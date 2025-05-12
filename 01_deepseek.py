

import os
import sqlite3
import psycopg2
import time
from dotenv import load_dotenv
from openai import OpenAI
import json
import re
import tiktoken
import os
import sys
import logging
from datetime import datetime, time, timedelta, timezone
import time as time_module


# Load environment variables
load_dotenv()

def setup_logger(log_folder="./logs", prefix="run"):
    # Ensure log directory exists
    os.makedirs(log_folder, exist_ok=True)

    # Create timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_folder, f"{prefix}_{timestamp}.log")

    # Set up root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))

    # Avoid adding handlers multiple times
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    # Redirect print() to logger
    class LoggerWriter:
        def write(self, message):
            message = message.strip()
            if message:
                logger.info(message)

        def flush(self):
            pass

    sys.stdout = LoggerWriter()
    sys.stderr = LoggerWriter()

    print(f"📁 Logging to: {log_filename}")
    return log_filename


def store_issue_result(conn, cursor, project_id, criterion, response_string, issue_number):
    placeholder = '?' if cursor.connection.__class__.__module__.startswith('sqlite3') else '%s'
    # Step 1: Clean and parse the response string
    cleaned = re.sub(r"^```json|```$", "", response_string.strip(), flags=re.IGNORECASE).strip()
    try:
        result_obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return

    # Step 2: Add issue_number to the object
    result_obj["issue_number"] = issue_number

    # Step 3: Check if the row exists
    cursor.execute(f"""
        SELECT issue_ids
        FROM project_top_attributes_v2
        WHERE project_id = {placeholder} AND criterion = {placeholder}
    """, (project_id, criterion))
    row = cursor.fetchone()

    if row:
        # Step 4a: Update existing row
        issue_ids = row[0]
        issue_ids.append(result_obj)
        cursor.execute(f"""
            UPDATE project_top_attributes_v2
            SET issue_ids = {placeholder}
            WHERE project_id = {placeholder} AND criterion = {placeholder}
        """, (json.dumps(issue_ids), project_id, criterion))
    else:
        # Step 4b: Insert new row
        cursor.execute(f"""
            INSERT INTO project_top_attributes_v2 (project_id, criterion, issue_ids)
            VALUES ({placeholder}, {placeholder}, {placeholder})
        """, (
            project_id,
            criterion,
            json.dumps([result_obj])
        ))
        
    conn.commit()
    
    
def truncate_issue_text(issue_text, command, max_total_tokens=60000):
    enc = tiktoken.get_encoding("cl100k_base")  # Best match for DeepSeek

    command_tokens = enc.encode(command)
    available_tokens = max_total_tokens - len(command_tokens)

    issue_tokens = enc.encode(issue_text)
    if len(issue_tokens) > available_tokens:
        print(f"⚠️ Truncating issue_text from {len(issue_tokens)} to {available_tokens} tokens.")
        issue_tokens = issue_tokens[:available_tokens]

    safe_issue_text = enc.decode(issue_tokens)
    return f"{command.strip()}\n\n---\n{safe_issue_text.strip()}\n---"


def query_llm(issue_text, command, provider="deepseek", model="deepseek-chat"):
    prompt = truncate_issue_text(issue_text, command)

    if provider == "openai":
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    elif provider == "deepseek":
        client = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
        )
    else:
        raise ValueError("Unsupported provider")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a software engineering assistant. Analyze GitHub issues."},
            {"role": "user", "content": prompt}
        ],
        stream=False,
        temperature=0.2
    )

    return response.choices[0].message.content.strip()


# returns a db connection
def get_db_connection(DBMS):
    if DBMS == 'SQLITE':
        conn = sqlite3.connect(os.getenv('DB_PATH'))
    elif DBMS == 'POSTGRES':
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT')
        )
    else:
        raise ValueError("Unsupported DBMS")
    return conn


def get_quality_attributes(cursor):
    cursor.execute("SELECT attribute, definition, related_words FROM quality_attributes_v2 ORDER BY turn ASC LIMIT 10")
    attributes = []
    for row in cursor.fetchall():
        criterion = row[0].strip()
        definition = row[1].strip()
        synonyms = [s.strip() for s in row[2]] if row[2] else []
        attributes.append({'criterion': criterion, 'synonyms': synonyms, 'definition': definition})
    return attributes


def get_projects(cursor, offset, limit):
    placeholder = '?' if cursor.connection.__class__.__module__.startswith('sqlite3') else '%s'
    query = f"""
        SELECT ci.project_id, COUNT(ci.issue_id) AS issue_count
        FROM combined_issues ci 
        GROUP BY ci.project_id
        HAVING COUNT(ci.issue_id) > 1000
        ORDER BY issue_count DESC
        LIMIT {placeholder} OFFSET {placeholder}
    """
    cursor.execute(query, (limit, offset))
    return [row[0] for row in cursor.fetchall()]


def process_project(conn, cursor, project_id, attributes):
    placeholder = '?' if cursor.connection.__class__.__module__.startswith('sqlite3') else '%s'

    for attr in attributes:
        criterion = attr["criterion"]
        
        cursor.execute(f"""
            SELECT *
            FROM project_top_attributes_v2
            WHERE project_id = {placeholder} AND criterion = {placeholder}
        """, (project_id, criterion))
        row = cursor.fetchone()
        
        if row:
            continue
        
        definition = attr["definition"]
        keywords = [criterion] + attr.get("synonyms", [])
        query_conditions = " OR ".join([f"issue_text ILIKE {placeholder}" for _ in keywords])
        query = f"""
            SELECT ci.issue_id, ci.issue_text, ci.number
            FROM combined_issues ci
            WHERE ci.size > 1000 AND ci.project_id = {placeholder} AND ({query_conditions})
            ORDER BY ci.size DESC
            LIMIT 4
        """
        params = [project_id] + [f"%{kw}%" for kw in keywords]
        cursor.execute(query, params)
        results = cursor.fetchall()

        if results:
            print(f"\n🔎 Attribute: {criterion}")
            for issue_id, issue_text, issue_number in results:
                print(f"\n🔎 Project: {project_id}, Issue: {issue_id}")
                # Construct prompt
                command = (
                    f"'{criterion}' defines as \"{definition}\" "
                    f"Extract the exact excerpt related to '{criterion}' from the following issue text. "
                    f"Return only a JSON object with two properties: 'reason' and 'score'. "
                    f"'reason' should contain the most relevant excerpt, with no explanation. "
                    f"'score' should be a sentiment value with two decimal places between -1 and +1. "
                    f"-1 means the entire provided issue text speaks negatively about the project in relation to '{criterion}', "
                    f"and +1 means the project is described as having the best features related to '{criterion}'."
                )
                
                response = query_llm(issue_text, command, model="deepseek-reasoner")
                print(f"Result: {response}")
                store_issue_result(conn, cursor, project_id, criterion, response, issue_number)


def to_bool(value):
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def main():
    # make a log file to capture all prints
    setup_logger()
    
    use_discount = not to_bool(os.getenv('DEBUG_MODE'))
    
    # Step 1: wait until 16:30 UTC
    now_utc = datetime.now(timezone.utc)
    start_time = now_utc.replace(hour=16, minute=30, second=0, microsecond=0)

    if use_discount and now_utc < start_time:
        wait_seconds = (start_time - now_utc).total_seconds()
        print(f"⏳ Waiting until 16:30 UTC ({int(wait_seconds)} seconds)...")
        time_module.sleep(wait_seconds)

    # Extract env values
    database = os.getenv('ACTIVE_DB')
    page_size = int(os.getenv('PAGE_SIZE', 10))  # ensure it's an int

    # connect to DB
    conn = get_db_connection(database)
    conn.autocommit = True
    cursor = conn.cursor()

    print("Collect attributes")
    attributes = get_quality_attributes(cursor)    

    # Step 2: process projects within allowed UTC window
    offset = 0
    while True:
        projects = get_projects(cursor, offset, page_size)
        if not projects:
            break

        for project_id in projects:
            now_utc = datetime.now(timezone.utc)

            if use_discount and now_utc.time() >= time(0, 0):
                print("⏹️ Reached 00:00 UTC — stopping further processing.")
                cursor.close()
                conn.close()
                return

            print(f"🕒 Processing project {project_id} at {now_utc.time().strftime('%H:%M:%S')} UTC")
            process_project(conn, cursor, project_id, attributes)

        offset += page_size

    cursor.close()
    conn.close()
    

if __name__ == '__main__':
    main()


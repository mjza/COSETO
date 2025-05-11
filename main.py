

import os
import sqlite3
import psycopg2
import time
from dotenv import load_dotenv
from openai import OpenAI
import json
import re
import psycopg2.extras


# Load environment variables
load_dotenv()


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

def query_llm(issue_text, command, provider="deepseek", model="deepseek-chat"):
    prompt = f"{command.strip()}\n\n---\n{issue_text.strip()}\n---"

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
    cursor.execute("SELECT attribute, definition, related_words FROM quality_attributes_v2 ORDER BY \"order\" ASC LIMIT 10")
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
    # Extract env values
    #debug_mode = to_bool(os.getenv('DEBUG_MODE'))
    database = os.getenv('ACTIVE_DB')
    page_size = os.getenv('PAGE_SIZE')
    
    # connect to DB
    conn = get_db_connection(database)
    conn.autocommit = True
    cursor = conn.cursor()
    
    print("Collect attributes")
    
    # retrieve attributes
    attributes = get_quality_attributes(cursor)
        
    offset = 0
    while True:
        projects = get_projects(cursor, offset, page_size)
        if not projects:
            break
        for project_id in projects:
            process_project(conn, cursor, project_id, attributes)
        offset += page_size

    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()




import os
import sqlite3
import psycopg2
import time
from sys import platform
from selenium.webdriver import ChromeOptions, Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from openai import OpenAI


# Load environment variables
load_dotenv()


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
    cursor.execute("SELECT criteria, synonyms FROM quality_attributes")
    attributes = []
    for row in cursor.fetchall():
        criteria = row[0].strip()
        synonyms = [s.strip() for s in row[1].split(',')] if row[1] else []
        attributes.append({'criteria': criteria, 'synonyms': synonyms})
    return attributes


def get_projects(cursor, offset, limit):
    placeholder = '?' if cursor.connection.__class__.__module__.startswith('sqlite3') else '%s'
    query = f"""
        SELECT id, repository_url 
        FROM projects 
        WHERE repository_url IS NOT NULL 
        ORDER BY issue_count DESC
        LIMIT {placeholder} OFFSET {placeholder}
    """
    cursor.execute(query, (limit, offset))
    return cursor.fetchall()


def search_github_issues(driver, issues_url, query):
    try:
        driver.get(issues_url)
        time.sleep(2)
        
        # Optionally check the result count from the metadata if it has any issue
        try:
            count_element = WebDriverWait(driver, 1).until(
                EC.presence_of_element_located((By.XPATH, "//*[@id=':rb:-list-view-metadata']/div[1]/ul/li[1]/a/span[1]"))
            )
            if count_element and count_element.text.strip().isdigit():
                if int(count_element.text.strip()) == 0:
                    return None
        except:
            pass  # If the element doesn't exist, fallback to checking link list
        
        search_input = driver.find_element(by=By.XPATH, value="//*[@id='repository-input']")
        if platform == "darwin":
            search_input.send_keys(Keys.COMMAND, "a")
        else:
            search_input.send_keys(Keys.CONTROL, "a")
        search_input.send_keys(Keys.BACKSPACE)
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        time.sleep(2)
        return driver.find_elements(By.CSS_SELECTOR, "a.IssuePullRequestTitle-module__ListItemTitle_1--_xOfg")
    except Exception as e:
        print(f"⚠️  Error searching '{query}' on {issues_url}: {e}")
        return []


def process_repository(driver, repo_url, attributes):
    issues_url = repo_url.rstrip('/') + "/issues"
    original_window = driver.current_window_handle

    for attr in attributes:
        q_main = f'is:issue is:open sort:created-desc {attr["criteria"]}'
        results = search_github_issues(driver, issues_url, q_main)
        
        # When there is no issue, don't try other attributes
        if results == None :
            return

        if not results and attr["synonyms"]:
            for syn in attr["synonyms"]:
                q_syn = f'is:issue is:open sort:created-desc {syn}'
                results = search_github_issues(driver, issues_url, q_syn)
                if results:
                    break

        if results:
            print(f"\n🔎 Attribute: {attr['criteria']} — Repo: {repo_url}")
            for issue in results:
                href = issue.get_attribute("href")
                if not href:
                    continue

                # Open in new tab
                driver.execute_script(f"window.open('{href}', '_blank');")
                time.sleep(2)

                # Switch to new tab
                new_window = [w for w in driver.window_handles if w != original_window][0]
                driver.switch_to.window(new_window)
                time.sleep(5)

                try:
                    issue_div = driver.find_element(By.CSS_SELECTOR, 'div[data-testid="issue-viewer-container"]')
                    print(f"\n🌐 {href}")
                    issue_text = issue_div.text.strip()
                    command = (
                        f"Extract the exact excerpt related to '{attr}' from the following issue text. "
                        f"Return only a JSON object with two properties: 'reason' and 'score'. "
                        f"'reason' should contain the most relevant excerpt, with no explanation. "
                        f"'score' should be a sentiment value with two decimal places between -1 and +1. "
                        f"-1 means the entire provided text speaks negatively about the project in relation to '{attr}', "
                        f"and +1 means the project is described as having the best features related to '{attr}'."
                    )
                    response = query_llm(issue_text, command)
                    print(response)
                    time.sleep(30)
                except Exception as e:
                    print(f"❌ Could not analyze body for {href}: {e}")

                # Close tab and switch back
                driver.close()
                driver.switch_to.window(original_window)



def create_driver(debug):
	options = ChromeOptions()

	if debug == False:
		options.add_argument('--headless')  # Run in background
		options.add_argument('--disable-gpu')  # Optional for headless stability
	else: 
		options.add_experimental_option("detach", True)
		options.headless = True
		options.add_experimental_option("excludeSwitches", ["enable-logging"])

	driver = Chrome(options=options)
	return driver


def to_bool(value):
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def main():
    # Extract env values
    debug_mode = to_bool(os.getenv('DEBUG_MODE'))
    database = os.getenv('ACTIVE_DB')
    page_size = os.getenv('PAGE_SIZE')
    
    # connect to DB
    conn = get_db_connection(database)
    cursor = conn.cursor()
    
    # retrieve attributes
    attributes = get_quality_attributes(cursor)
    
    # make browser driver
    driver = create_driver(debug_mode)
    
    offset = 0
    while True:
        projects = get_projects(cursor, offset, page_size)
        if not projects:
            break
        for project_id, repo_url in projects:
            process_repository(driver, repo_url, attributes)
        offset += page_size

    driver.quit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()











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


def to_bool(value):
    return str(value).strip().lower() in ("true", "1", "yes", "on")


# Load environment variables
load_dotenv()


# how many projects to process per page
DATABASE = os.getenv('ACTIVE_DB')  
PAGE_SIZE = os.getenv('PAGE_SIZE')
DEBUG_MODE = to_bool(os.getenv('DEBUG_MODE'))

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
        q_main = f'is:issue sort:created-desc {attr["criteria"]}'
        results = search_github_issues(driver, issues_url, q_main)
        
        # When there is no issue, don't try other attributes
        if results == None :
            return

        if not results and attr["synonyms"]:
            for syn in attr["synonyms"]:
                q_syn = f'is:issue sort:created-desc {syn}'
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
                    print(issue_div.text.strip())
                    time.sleep(5)
                except Exception as e:
                    print(f"❌ Could not read body for {href}: {e}")

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


def main():
    conn = get_db_connection(DATABASE)
    cursor = conn.cursor()
    attributes = get_quality_attributes(cursor)

    driver = create_driver(DEBUG_MODE)

    offset = 0
    while True:
        projects = get_projects(cursor, offset, PAGE_SIZE)
        if not projects:
            break
        for project_id, repo_url in projects:
            process_repository(driver, repo_url, attributes)
        offset += PAGE_SIZE

    driver.quit()
    cursor.close()
    conn.close()


if __name__ == '__main__':
    main()









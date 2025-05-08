# COSETO
A COmponent SElector TOol

# How to run the program

## Prerequirements
- Supported browser: Google Chrome
- Supported Operating Systems: Windows, and MacOS
- To run the application, you need to download chromedriver.
- Download `chromedriver` from [here](https://googlechromelabs.github.io/chrome-for-testing/#stable).
- Extract the chromedriver file and paste it into the same folder as this repository.
- It is important that "COSETO.exe" and "chromedriver.exe" are in the same folder.
- Double click on "COSETO.exe" and follow the prompts on the screen

## Creating the Virtual Environment
First, navigate to your project's root directory in your terminal. Then, create a virtual environment named venv (or another name of your choice) by running:

```
python -m venv venv
```

This command creates a new directory named venv in your project directory, which contains a copy of the Python interpreter, the standard library, and various supporting files.

## Activating the Virtual Environment
Before you can start installing packages, you need to activate the virtual environment. 
Activation will ensure that the Python interpreter and tools within the virtual environment are used in preference to the system-wide Python installation.

1. **On macOS and Linux:**

```
source venv/bin/activate
```

2. **On Windows (cmd.exe):**

```
.\venv\Scripts\activate.bat
```

3. **On Windows (PowerShell) or VSC Terminal:**

```
.\venv\Scripts\Activate.ps1
```

Once activated, your terminal prompt must change to indicate that the virtual environment is active.

## Installing Dependencies

If you want to install all requirements at once use the following instruction with the virtual environment activated:

```bash
pip install -r requirements.txt
```

Otherwise follow the next section for installing required libraries step by step.

### Install Dependencies one by one 

Libraries needed to run the Python code:

To install Selenium:
```
python -m pip install selenium==4.2.0
```

To install pyautogui:
```
python -m pip install pyautogui
```

To install pyinstaller:
```
python -m pip install pyinstaller
```

To install keyboard:
```
python -m pip install keyboard
```

With these libraries installed, you can then modify the source code and run it as a python file.



## Environment Variables
Make a copy of the `template.env` and rename it to `.env`, then copy and paste your provided secret keys into the file.

```bash

```

## Start/Run the App
Use the following command to run the application:
```
python main.py
```

This will open the github page in your default browser.



## Trouble shooting

- Please note if you face an error like the following, it means you need to download a newer version of `chromedriver` or on the other word update it. 

```bash
C:\Users\mahdi\Git\GitHub\COSETO>COSETO.exe
Traceback (most recent call last):
  File "COSETO.py", line 303, in <module>
    driver = create_driver()
             ^^^^^^^^^^^^^^^
  File "COSETO.py", line 156, in create_driver
    driver = Chrome(options=options)
             ^^^^^^^^^^^^^^^^^^^^^^^
  File "selenium\webdriver\chrome\webdriver.py", line 70, in __init__
  File "selenium\webdriver\chromium\webdriver.py", line 92, in __init__
  File "selenium\webdriver\remote\webdriver.py", line 275, in __init__
  File "selenium\webdriver\remote\webdriver.py", line 365, in start_session
  File "selenium\webdriver\remote\webdriver.py", line 430, in execute
  File "selenium\webdriver\remote\errorhandler.py", line 247, in check_response
selenium.common.exceptions.SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version 121
Current browser version is 123.0.6312.58 with binary path C:\Program Files\Google\Chrome\Application\chrome.exe
Stacktrace:
        GetHandleVerifier [0x00007FF605A55E42+3538674]
        (No symbol) [0x00007FF605674C02]
        (No symbol) [0x00007FF605525AEB]
        (No symbol) [0x00007FF60555C512]
        (No symbol) [0x00007FF60555B872]
        (No symbol) [0x00007FF605555106]
        (No symbol) [0x00007FF6055521C8]
        (No symbol) [0x00007FF6055994B9]
        (No symbol) [0x00007FF60558EE53]
        (No symbol) [0x00007FF60555F514]
        (No symbol) [0x00007FF605560631]
        GetHandleVerifier [0x00007FF605A86CAD+3738973]
        GetHandleVerifier [0x00007FF605ADC506+4089270]
        GetHandleVerifier [0x00007FF605AD4823+4057299]
        GetHandleVerifier [0x00007FF6057A5C49+720121]
        (No symbol) [0x00007FF60568126F]
        (No symbol) [0x00007FF60567C304]
        (No symbol) [0x00007FF60567C432]
        (No symbol) [0x00007FF60566BD04]
        BaseThreadInitThunk [0x00007FFFEEE27344+20]
        RtlUserThreadStart [0x00007FFFF03626B1+33]

[19088] Failed to execute script 'COSETO' due to unhandled exception!
```




#### Generate executable file from the python file

On the command window:

1. Go to the directory where you download this repository.
2. While hovering your mouse in the folder, Right Click -> Open in Terminal
3. This will open a black Windows PowerShell.
4. Paste the following code and press Enter to run: 
```
pyinstaller --onefile COSETO.py
```
5. After the code has executed, it will create a "build" and "dist" folder in the directory.
6. Go to the "dist" folder.
7. Copy the executable file, and paste it in to the main folder by clicking back.
8. Run the executable file by double clicking on it.

#### Enter login data by file
1. Make a copy of `env.txt` file
2. Rename it to `env.lcl`
3. Update values inside of it
4. Save and run the `COSETO.exe` again.
Create a env
python -m venv venv

Activate venv
(Powershell)
.\venv\Scripts\activate 

(Command Prompt)
.\venv\Scripts\activate.bat

Install the libraries
pip install -r requirements.txt

now start the backend using command
uvicorn app.main:app --reload

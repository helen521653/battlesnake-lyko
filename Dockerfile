FROM python:3.12-slim

WORKDIR /usr/app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install app
COPY snake ./snake
COPY main.py server.py ./

ENV PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000

# Run Battlesnake
CMD [ "python", "main.py" ]

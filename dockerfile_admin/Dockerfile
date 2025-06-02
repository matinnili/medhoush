FROM python:3.10

# Set environment variables for pip
WORKDIR /app

COPY requirements.txt requirements.txt
COPY medhoush_telegram_2.0.0_admin.py medhoush_telegram_2.0.0_admin.py
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .

CMD python3  medhoush_telegram_2.0.0_admin.py
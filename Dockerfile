# 1. Use a lightweight Python operating system
FROM python:3.11-slim

# 2. Set the working directory inside the shipping container
WORKDIR /app

# 3. Copy your requirements and install the security-patched packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your Forecast Lab code into the container
COPY . .

# 5. Open the specific network port that Streamlit uses
EXPOSE 8501

# 6. The command the server runs to boot up the app
CMD ["streamlit", "run", "forecast_map.py", "--server.port=8501", "--server.address=0.0.0.0"]
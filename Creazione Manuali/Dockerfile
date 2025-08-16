# Dockerfile per Creazione Manuali
FROM python:3.11-slim

WORKDIR /app

# Copia requirements e codice
COPY requirements.txt ./
COPY generate_manual.py ./
COPY service_account_key.json ./
COPY openai_config.json ./

# Installa le dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Crea directory per i log
RUN mkdir -p /var/log/app

# Imposta le variabili d'ambiente
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Esponi la porta
EXPOSE 8080

# Comando di avvio
ENTRYPOINT ["python", "generate_manual.py"]
CMD ["serve"] 
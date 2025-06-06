FROM python:3.10-slim

WORKDIR /app

# Instalar herramientas necesarias
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Descargar Archy y enlazar el binario directamente
RUN curl -L https://sdk-cdn.mypurecloud.com/archy/latest/archy-linux.zip -o archy.zip \
    && unzip archy.zip -d /opt/archy \
    && chmod +x /opt/archy/archyBin/archy-linux-* \
    && ln -s /opt/archy/archyBin/archy-linux-* /usr/local/bin/archy \
    && mkdir -p /opt/archy/debug \
    && rm archy.zip

# Agregar Archy al PATH
ENV PATH="/opt/archy:${PATH}"
ENV PATH="/usr/local/bin:${PATH}"
# Copiar archivos del proyecto
COPY . .

# Instalar dependencias de Python
RUN pip install --no-cache-dir \
    streamlit==1.45.0 \
    pandas \
    ruamel.yaml \
    openpyxl \
    rapidfuzz

# Setear PYTHONPATH
ENV PYTHONPATH=/app

EXPOSE 8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]

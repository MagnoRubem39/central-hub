FROM ubuntu:22.04

# Define diretório de trabalho
WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    libgl1-mesa-glx \
    libgtk-3-0 \
    libpq-dev \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libgstreamer-plugins-good1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-libav \
    gstreamer1.0-x \
    libmpv1 \
    python3 \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copia requirements.txt
COPY requirements.txt .

# Instala as dependências Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Copia o restante da aplicação
COPY . .

# Comando padrão ao iniciar o container (altere conforme seu app)
CMD ["python3", "app.py"]

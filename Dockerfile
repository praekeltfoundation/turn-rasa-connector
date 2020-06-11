FROM rasa/rasa:1.10.2
WORKDIR /turn-rasa-connector
COPY requirements.txt ./

# Use root user for installing dependancies
USER root
RUN pip install -r requirements.txt
COPY . ./
RUN pip install -e .

USER 1001
WORKDIR /app

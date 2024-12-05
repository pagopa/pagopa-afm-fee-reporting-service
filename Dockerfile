FROM python:3.11@sha256:2c80c66d876952e04fa74113864903198b7cfb36b839acb7a8fef82e94ed067c

WORKDIR /app
COPY . /app
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
ENV PYTHONUNBUFFERED=0
CMD ["python", "-u", "src/fee-report-builder.py"]
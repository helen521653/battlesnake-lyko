# Змейка без внешних зависимостей: только стандартная библиотека Python.
FROM python:3.12-slim
WORKDIR /app
COPY snake ./snake
COPY server.py ./
ENV PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "server.py"]

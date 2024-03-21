# Base image with vscode frontend for web browser
FROM python:3.11-slim
# Copy project to image
COPY . /vpy
# Switch to project directory
WORKDIR /vpy
# Install compiler to python PATH
RUN pip install .
# Set entry point
ENTRYPOINT [ "vpy" ]
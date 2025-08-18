# Set base image (host OS)
FROM public.ecr.aws/lambda/python:3.12

ENV AWS_LAMBDA=true

# Install build dependencies
RUN dnf update -y && \
    dnf install -y gcc gcc-c++ make && \
    dnf clean all

# Copy the dependencies and setup files to the working directory
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
COPY setup.py ${LAMBDA_TASK_ROOT}/
COPY setup.cfg ${LAMBDA_TASK_ROOT}/

# Upgrade pip and install Python dependencies
RUN cd ${LAMBDA_TASK_ROOT} && \
    pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the newvelles package
COPY newvelles/ ${LAMBDA_TASK_ROOT}/newvelles/

# Copy data files to the expected location
COPY data/ ${LAMBDA_TASK_ROOT}/data/

# Install the package
RUN cd ${LAMBDA_TASK_ROOT} && pip install -e .

# Download spaCy model after package installation
RUN python -m spacy download en_core_web_sm 

# Copy handler function
COPY handler.py ${LAMBDA_TASK_ROOT}/

# Overwrite the command by providing a different command directly in the template.
CMD ["handler.handler"]

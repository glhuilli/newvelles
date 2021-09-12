# Set base image (host OS)
FROM public.ecr.aws/lambda/python:3.8

ENV AWS_LAMBDA=true

# Copy the dependencies file to the working directory
ADD newvelles ${LAMBDA_TASK_ROOT}/newvelles
ADD requirements.txt ${LAMBDA_TASK_ROOT}
ADD setup.py ${LAMBDA_TASK_ROOT}
ADD data/rss_source_short.txt ${LAMBDA_TASK_ROOT}

# Install dependencies
RUN cd ${LAMBDA_TASK_ROOT} && python setup.py install

# Download library for NLP 
RUN python -m spacy download en_core_web_sm 

# Copy handler function
COPY  handler.py ${LAMBDA_TASK_ROOT}

# Overwrite the command by providing a different command directly in the template.
CMD ["handler.handler"]

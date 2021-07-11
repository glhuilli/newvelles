# Set base image (host OS)
FROM public.ecr.aws/lambda/python:3.8


# Copy the dependencies file to the working directory
ADD newvelles ${LAMBDA_TASK_ROOT}/newvelles
ADD requirements.txt ${LAMBDA_TASK_ROOT}
ADD setup.py ${LAMBDA_TASK_ROOT}

RUN cd ${LAMBDA_TASK_ROOT} && python setup.py install

# Copy handler function
COPY  app.py ${LAMBDA_TASK_ROOT}

# Overwrite the command by providing a different command directly in the template.
CMD ["handler.handler"]

# create new build 
docker build -t docker-lambda-newvelles:v1 .

# test new build
docker run -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION  -d -p 8080:8080 docker-lambda-newvelles:v1

# add tag for ECR 
docker tag docker-lambda-newvelles:v1 $1.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda

# login to ECR 
sh bin/ecr.sh

# push to ECR
docker push $1.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda



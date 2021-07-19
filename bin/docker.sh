# create new build 
docker build -t docker-lambda-newvelles:v1 .

# add tag for ECR 
docker tag docker-lambda-newvelles:v1 617641631577.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda

# login to ECR 
sh bin/ecr.sh

# push to ECR
docker push 617641631577.dkr.ecr.us-west-2.amazonaws.com/newvelles-docker-lambda



#!/bin/bash

set -ex

# change to the directory containing this script
cd "$( dirname "${BASH_SOURCE[0]}" )"

# fetch the latest version of each base image from AWS ECR Public
for image in 'public.ecr.aws/ubuntu/ubuntu:jammy' 'public.ecr.aws/ubuntu/ubuntu:noble' 'public.ecr.aws/ubuntu/ubuntu:resolute' 'public.ecr.aws/amazonlinux/amazonlinux:2023'; do
    docker pull ${image}
done

for image in 'jammy' 'noble' 'resolute' 'amazon-linux2023' 'amazon-linux2023-py311' 'amazon-linux2023-py313'; do
    docker build -t wheel-tester/${image} -f docker/Dockerfile.${image} .
done

image=testhost
docker build -t wheel-tester/${image} -f docker/Dockerfile.${image} \
           --build-arg USER_GID="$(id -g)" \
           --build-arg USER_UID="$(id -u)" \
           --build-arg USER_NAME="$(whoami)" \
           --build-arg DOCKER_GID="$(stat -c '%g' /var/run/docker.sock)" \
           .
#docker image prune -y

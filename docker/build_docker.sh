#!/bin/bash

#we need to step out to expand the build context
cd ..

#training container
#nvidia-docker build -t tkurth/pytorch-bias_gan:latest .
nvidia-docker build -t gitlab-master.nvidia.com:5005/tkurth/mlperf-deepcam:debug -f docker/Dockerfile.train .
docker push gitlab-master.nvidia.com:5005/tkurth/mlperf-deepcam:debug

#tag for NERSC registry
docker tag gitlab-master.nvidia.com:5005/tkurth/mlperf-deepcam:debug registry.services.nersc.gov/tkurth/mlperf-deepcam:debug
docker push registry.services.nersc.gov/tkurth/mlperf-deepcam:debug

#profiling container (public)
nvidia-docker build -t registry.services.nersc.gov/tkurth/mlperf-deepcam:profile -f docker/Dockerfile.profile.public .
docker push registry.services.nersc.gov/tkurth/mlperf-deepcam:profile

#profiling container (internal)
nvidia-docker build -t gitlab-master.nvidia.com:5005/tkurth/mlperf-deepcam:profile_internal -f docker/Dockerfile.profile.internal .
docker push gitlab-master.nvidia.com:5005/tkurth/mlperf-deepcam:profile_internal

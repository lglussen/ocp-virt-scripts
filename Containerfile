FROM registry.redhat.io/web-terminal/web-terminal-tooling-rhel8:1.8
USER root

RUN curl -LI https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -o /usr/local/bin/yq \
    && chmod 775 /usr/local/bin/yq 
RUN microdnf install git -y
USER user
RUN git clone git@github.com:lglussen/ocp-virt-scripts.git
WORKDIR /home/user/ocp-virt-scripts

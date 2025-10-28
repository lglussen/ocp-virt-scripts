FROM registry.redhat.io/web-terminal/web-terminal-tooling-rhel8:1.8
USER root

RUN microdnf install wget -y
RUN wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq \
    && chmod 775 /usr/local/bin/yq 
RUN microdnf install git python3-pip python3-pyyaml -y 
RUN adduser --uid 1001 user
RUN git clone https://github.com/lglussen/ocp-virt-scripts.git
RUN chown -R user:0 /home/user
USER user
WORKDIR /home/user/ocp-virt-scripts

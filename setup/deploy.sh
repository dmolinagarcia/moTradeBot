#!/bin/bash
## Generating RSA Keys
export MOTRADE_ID=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 6 ; echo '')

mkdir .ssh
ssh-keygen -b 2048 -t rsa -f .ssh/id_rsa_${MOTRADE_ID} -q -N ""
chmod 700 .ssh
chmod 600 .ssh/id_rsa_${MOTRADE_ID}

## OCI_TENANCY contains the current tenancy
echo Creating moTrade proBox infrastructure ...
export COMPARTMENT_NAME='moTrade_${MOTRADE_ID}'
export COMPUTE_NAME='moTrade_${MOTRADE_ID}_probox'
## export COMPUTE_SHAPE='VM.Standard.A1.Flex'          ## ARM instances not supported yet
export COMPUTE_SHAPE='VM.Standard.E2.1.Micro'
export USER_HOME=$(eval echo ~)

exit 0

echo "Search for available availability domains ..."
for AD in 1 2 3
do
  ad=$(oci iam availability-domain list --query "(data[?ends_with(name, '-$AD')] | [0].name) || data[0].name" --raw-output)
  oci compute shape list -c $OCI_TENANCY --availability-domain $ad | grep $COMPUTE_SHAPE >> /dev/null
  if [ $? -eq 0 ]
  then
    export AVAILABILITY_DOMAIN=$(oci iam availability-domain list --query "(data[?ends_with(name, '-$AD')] | [0].name) || data[0].name" --raw-output)
  fi
done
export AVAILABILITY_DOMAIN=$(oci iam availability-domain list --query "(data[?ends_with(name, '-3')] | [0].name) || data[0].name" --raw-output)

# Search for ubunto 20.04 image

oci compute image list -c $OCI_TENANCY --query "(data[?contains('display-name', 'Canonical-Ubuntu-20.04')])"

export IMAGE_ID='ocid1.image.oc1.eu-frankfurt-1.aaaaaaaaevqvpysi6itvzw2wks7zlopyroyfe5vvm5pfspk433tax452vhoq'     ## ARM instances not supported yet
export IMAGE_ID='ocid1.image.oc1.eu-frankfurt-1.aaaaaaaaose3uwyt7kyumj35pdjj7ww4xumzpittbo3g5mezmmicvms2aqwq'

echo moTradeID: $MOTRADE_ID
echo Compartment Name: $COMPARTMENT_NAME
echo Compute Node Name: $COMPUTE_NAME
echo Compute Shape: $COMPUTE_SHAPE
echo Availability Domain: $AVAILABILITY_DOMAIN

## COMPARTMENT
echo Checking if compartment $COMPARTMENT_NAME exists...
export COMPARTMENT_ID=$(oci iam compartment list --query "data[?name=='${COMPARTMENT_NAME}'].id | [0]" --raw-output 2> /dev/null)
if [ -z $COMPARTMENT_ID ]
then 
    echo Compartment does not exist. Creating compartment now...
    export COMPARTMENT_ID=$(oci iam compartment create -c $OCI_TENANCY --name "$COMPARTMENT_NAME" --description "moTrade Compartment" --query "data.id" --raw-output)
fi
until oci iam compartment get -c $COMPARTMENT_ID >> /dev/null 2> /dev/null
do 
    echo Waiting for compartment to become AVAILABLE...
    sleep 5
done

echo Compartment ID: $COMPARTMENT_ID

## VCN
echo Creating VCN...
export VCN_ID=$(oci network vcn create -c $COMPARTMENT_ID --cidr-block "10.0.0.0/16" --query "data.id" --raw-output)
until oci network vcn get --vcn-id $VCN_ID >> /dev/null 2> /dev/null
do
    echo Waiting for VCN to become AVAILABLE...
    sleep 3
done

echo VCN ID: $VCN_ID

export SUBNET_ID=$(oci network subnet create --vcn-id ${VCN_ID} -c ${COMPARTMENT_ID} --cidr-block "10.0.0.0/24" --query "data.id" --raw-output)
export IG_ID=$(oci network internet-gateway create -c ${COMPARTMENT_ID} --is-enabled true --vcn-id ${VCN_ID} --query "data.id" --raw-output)
export RT_ID=$(oci network route-table list -c ${COMPARTMENT_ID} --vcn-id ${VCN_ID} --query "data[0].id" --raw-output)
oci network route-table update --rt-id ${RT_ID} --route-rules '[{"cidrBlock":"0.0.0.0/0","networkEntityId":"'${IG_ID}'"}]' --force >> /dev/null 2> /dev/null

echo Subnet ID: $SUBNET_ID
echo Internet Gateway ID: $IG_ID
echo Route Table ID: $RT_ID

## COMPUTE INSTANCE
echo Creating Compute node...
export COMPUTE_OCID=$(oci compute instance launch \
 --compartment-id ${COMPARTMENT_ID} \
 --shape "${COMPUTE_SHAPE}" \
 --display-name "${COMPUTE_NAME}" \
 --image-id "${IMAGE_ID}" \
 --ssh-authorized-keys-file "${USER_HOME}/.ssh/id_rsa.pub" \
 --subnet-id ${SUBNET_ID} \
 --availability-domain "${AVAILABILITY_DOMAIN}" \
 --assign-public-ip FALSE \
 --wait-for-state RUNNING \
 --query "data.id" \
 --raw-output)
 
# ## --shape-config '{"memoryInGBs":6, "ocpus":1}' \    For FLEX ARM instances. Not yet supported

sleep 15
echo Compute Node ID: $COMPUTE_OCID

echo Adding Public IP...
export VNIC_ID=$(oci compute instance list-vnics --instance-id $COMPUTE_OCID --query "data[0].id" --raw-output)
export PRIV_IP_ID=$(oci network private-ip list --vnic-id $VNIC_ID --query "data[0].id" --raw-output)
oci network public-ip create --compartment-id $COMPARTMENT_ID --lifetime RESERVED --private-ip-id $PRIV_IP_ID  --wait-for-state ASSIGNED >> /dev/null 2> /dev/null
sleep 15 

export PUBLIC_IP=$(oci network vnic get --vnic-id $VNIC_ID --query 'data."public-ip"' --raw-output)
echo Compute Node Public IP: $PUBLIC_IP

echo moTrade devBox infrastructure created!

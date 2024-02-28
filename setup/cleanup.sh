## Cleanup
export MOTRADE_ID=$1

echo Cleaning up moTrade proBox Infrastructure $MOTRADE_ID ...
export COMPARTMENT_NAME="moTrade_${MOTRADE_ID}"
export COMPARTMENT_ID=$(oci iam compartment list --query "data[?name=='${COMPARTMENT_NAME}'].id | [0]" --raw-output)
export VCN_ID=$(oci network vcn list -c $COMPARTMENT_ID --query "data[0].id" --raw-output)
export RT_ID=$(oci network route-table list --compartment-id $COMPARTMENT_ID --vcn-id $VCN_ID --query "data[0].id" --raw-output)
export IG_ID=$(oci network internet-gateway list --compartment-id $COMPARTMENT_ID --query "data[0].id" --raw-output)
export SUBNET_ID=$(oci network subnet list --compartment-id $COMPARTMENT_ID --vcn-id $VCN_ID --query "data[0].id" --raw-output)
export COMPUTE_OCID=$(oci compute instance list --compartment-id $COMPARTMENT_ID --query "data[0].id" --raw-output)
export PUBLIC_IP_ID=$(oci network public-ip list --compartment-id $COMPARTMENT_ID --scope REGION --all --query "data[0].id" --raw-output)
export USER_HOME=$(eval echo ~)

if [ ! -z $COMPUTE_OCID ]
then
    echo Cleaning up Compute Node... $COMPUTE_OCID
    oci compute instance terminate --instance-id $COMPUTE_OCID --force --wait-for-state TERMINATED >> /dev/null 2>> /dev/null
    sleep 15
    rm -rf ${USER_HOME}/.ssh/id_rsa_${MOTRADE_ID}*
fi



if [ ! -z $PUBLIC_IP_ID ]
then
    echo Cleaning up Public IP... $PUBLIC_IP_ID
    oci network public-ip delete --public-ip-id $PUBLIC_IP_ID --force
    sleep 15
fi

echo Cleaning up VCN components...
if [ ! -z $RT_ID ]
then
    oci network route-table update --rt-id ${RT_ID} --route-rules '[]' --force >> /dev/null 2>> /dev/null
fi

if [ ! -z $IG_ID ]
then
    oci network internet-gateway delete --ig-id $IG_ID --force
fi

if [ ! -z $SUBNET_ID ]
then
    oci network subnet delete --subnet-id $SUBNET_ID --force
fi

if [ ! -z $VCN_ID ]
then
    sleep 15
    echo Cleaning up VCN... $VCN_ID
    oci network vcn delete --vcn-id $VCN_ID --force  >> /dev/null 2>> /dev/null
    sleep 15
fi

if [ ! -z $COMPARTMENT_ID ]
then
    echo Cleaning up Compartment... $COMPARTMENT_ID
    oci iam compartment delete --compartment-id $COMPARTMENT_ID --force >> /dev/null 2>> /dev/null
fi

echo moTrade Infrastructure cleaned up!

# remove alias from bash_profile!

grep -v $MOTRADE_ID ~/.bash_profile > tmpfile && mv tmpfile ~/.bash_profile
read -p "APIKEY" vAPIKEY
read -p "SECRETKEY" vSECRETKEY

echo "Do you want to use your REAL account or your TEST account?"
select yn in "REAL" "TEST"; do
    case $yn in
        REAL ) vAPIURL="https://open-api-vst.bingx.com"; break;;
        TEST ) vAPIURL="https://open-api.bingx.com";;
    esac
done

APIURL = "$vAPIURL"
APIKEY = "$vAPIKEY"
SECRETKEY = "$vSECRETKEY"

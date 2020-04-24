# Setup and Install

Quick steps to set up and run Twins on AWS.

## AWS at FB

1. Get the script `aws-mfa` from the following link: [https://our.internmc.facebook.com/intern/paste/P127874924](https://our.internmc.facebook.com/intern/paste/P127874924)

2. Save the above script into a file `~/bin/aws-mfa`

3. The following command needs to be run every 24 hours, and using FB's VPN:
```
source ~/bin/aws-mfa
```

4. More info at [https://fb.quip.com/YrDyAS3GDcwZ](https://fb.quip.com/YrDyAS3GDcwZ)

## Install
1. Create a virtual env: 
```
python -m virtualenv venv
source venv/bin/activate
```

2. Install `boto3` and `fabric`:
```
pip install boto3
pip install fabric
```

3. Configure `awscli`:
```
pip install awscli
aws configure 	# input 'eu-north-1' as region
```

## Access Existing AWS Instances
1. Got to the AWS console interface and generate a new .pem key file

2. Extract the public key from the .pem key file:
```
ssh-keygen -f YOUR_KEY.pem -y > YOUR_KEY.pub
```

3. Send `YOUR_KEY.pub` to someone that has access to the machines so that they can add it to each machine:
```
./ssh/authorized_keys
```

## Run
1. Run the following command to get a list of all possible tasks:
```
fab --list
```

2. Run the following command, where <NAME> is the name of the desired task:
```
fab <NAME>
```

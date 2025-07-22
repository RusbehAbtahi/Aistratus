# create trust policy
cat > ./tl_upload_trust.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "ec2.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
JSON

# create bucket-write policy
cat > ./tl_upload_bucket_policy.json <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowLayerZipUpload",
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:PutObjectAcl"],
    "Resource": "arn:aws:s3:::lambda-layer-zip-108782059508/*"
  }]
}
JSON

# verify files exist
ls -l tl_upload_*json



# 1️⃣  create the role with the trust policy you just saved
aws iam create-role \
  --role-name tl-layer-build-upload \
  --assume-role-policy-document file://./tl_upload_trust.json

# 2️⃣  attach the inline bucket-write policy
aws iam put-role-policy \
  --role-name tl-layer-build-upload \
  --policy-name tl-layer-build-upload-s3-write \
  --policy-document file://./tl_upload_bucket_policy.json

# 3️⃣  create an instance-profile and add the role (EC2 can then assume it)
aws iam create-instance-profile \
  --instance-profile-name tl-layer-build-upload-ip

aws iam add-role-to-instance-profile \
  --instance-profile-name tl-layer-build-upload-ip \
  --role-name tl-layer-build-upload

# 4️⃣  verify everything
aws iam get-role --role-name tl-layer-build-upload --output json \
  --query '[Role.RoleName,Role.Arn]'

aws iam list-instance-profiles-for-role \
  --role-name tl-layer-build-upload \
  --output json --query 'InstanceProfiles[*].[InstanceProfileName,Arn]'

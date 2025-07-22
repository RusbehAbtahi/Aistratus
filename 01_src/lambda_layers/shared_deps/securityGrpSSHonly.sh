# Create SG “tl-layer-build-sg” in default VPC vpc-02f18bb006ed33d29
aws ec2 create-security-group \
  --group-name tl-layer-build-sg \
  --description "SSH access for one-off Lambda layer build" \
  --vpc-id vpc-02f18bb006ed33d29

# Authorise inbound IPv6 SSH *only* from your current address
aws ec2 authorize-security-group-ingress \
  --group-name tl-layer-build-sg \
  --ip-permissions '[{
      "IpProtocol":"tcp",
      "FromPort":22,
      "ToPort":22,
      "Ipv6Ranges":[{"CidrIpv6":"a02:810d:478b:ba00:20c5:e6c:97db:37ee/128"}]
  }]'

# Verify
aws ec2 describe-security-groups --group-names tl-layer-build-sg \
  --query '[].[GroupId,GroupName,VpcId,IpPermissions]' --output table

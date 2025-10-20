# Deployment Guide

Complete guide for deploying the Agentic AI Starter Template to AWS.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured (`aws configure`)
- Docker installed locally
- ECR repository created

## Local Development

### Using Docker Compose

1. **Start all services**
```bash
docker-compose -f deployment/docker-compose.yml up -d
```

2. **View logs**
```bash
docker-compose -f deployment/docker-compose.yml logs -f
```

3. **Stop services**
```bash
docker-compose -f deployment/docker-compose.yml down
```

## AWS Deployment

### Step 1: Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name agentic-ai \
  --region us-east-1
```

### Step 2: Build and Push Docker Image

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t agentic-ai -f deployment/Dockerfile .

# Tag image
docker tag agentic-ai:latest \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-ai:latest

# Push image
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-ai:latest
```

### Step 3: Create Secrets in AWS Secrets Manager

```bash
# OpenAI API Key
aws secretsmanager create-secret \
  --name agentic-ai/openai-api-key \
  --secret-string "your-openai-api-key"

# JWT Secret
aws secretsmanager create-secret \
  --name agentic-ai/jwt-secret \
  --secret-string "$(openssl rand -base64 32)"
```

### Step 4: Deploy CloudFormation Stack

```bash
aws cloudformation create-stack \
  --stack-name agentic-ai-production \
  --template-body file://deployment/aws/cloudformation.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=production \
    ParameterKey=VpcId,ParameterValue=vpc-xxxxx \
    ParameterKey=SubnetIds,ParameterValue=\"subnet-xxxxx,subnet-yyyyy\" \
    ParameterKey=ContainerImage,ParameterValue=ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-ai:latest \
  --capabilities CAPABILITY_IAM
```

### Step 5: Monitor Deployment

```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name agentic-ai-production \
  --query 'Stacks[0].StackStatus'

# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name agentic-ai-production \
  --query 'Stacks[0].Outputs'
```

### Step 6: Test Deployment

```bash
# Get Load Balancer URL
ALB_URL=$(aws cloudformation describe-stacks \
  --stack-name agentic-ai-production \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerURL`].OutputValue' \
  --output text)

# Test health endpoint
curl http://$ALB_URL/health
```

## Updating Deployment

### Update Application Code

```bash
# Build and push new image
docker build -t agentic-ai -f deployment/Dockerfile .
docker tag agentic-ai:latest \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-ai:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-ai:latest

# Update ECS service to use new image
aws ecs update-service \
  --cluster agentic-ai-production \
  --service agentic-ai-production \
  --force-new-deployment
```

### Update Infrastructure

```bash
aws cloudformation update-stack \
  --stack-name agentic-ai-production \
  --template-body file://deployment/aws/cloudformation.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=production \
    ParameterKey=VpcId,UsePreviousValue=true \
    ParameterKey=SubnetIds,UsePreviousValue=true \
    ParameterKey=ContainerImage,UsePreviousValue=true \
  --capabilities CAPABILITY_IAM
```

## Monitoring

### CloudWatch Logs

```bash
# View logs
aws logs tail /ecs/agentic-ai-production --follow
```

### CloudWatch Metrics

View metrics in AWS Console:
- ECS Service metrics
- Custom application metrics
- ALB metrics

### Alarms

CloudFormation creates alarms for:
- High CPU utilization (>80%)
- High memory utilization (>80%)

## Scaling

### Manual Scaling

```bash
aws ecs update-service \
  --cluster agentic-ai-production \
  --service agentic-ai-production \
  --desired-count 4
```

### Auto Scaling

Add auto-scaling configuration to CloudFormation template or use AWS Console.

## Troubleshooting

### Check ECS Task Status

```bash
aws ecs list-tasks \
  --cluster agentic-ai-production \
  --service-name agentic-ai-production

aws ecs describe-tasks \
  --cluster agentic-ai-production \
  --tasks TASK_ARN
```

### View Container Logs

```bash
aws logs get-log-events \
  --log-group-name /ecs/agentic-ai-production \
  --log-stream-name api/CONTAINER_ID
```

### Common Issues

1. **Task fails to start**: Check IAM roles and secrets access
2. **Health check fails**: Verify application is listening on port 8000
3. **High memory usage**: Increase task memory in CloudFormation

## Cleanup

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name agentic-ai-production

# Delete ECR images
aws ecr batch-delete-image \
  --repository-name agentic-ai \
  --image-ids imageTag=latest

# Delete secrets
aws secretsmanager delete-secret \
  --secret-id agentic-ai/openai-api-key \
  --force-delete-without-recovery
```

## Security Best Practices

1. **Use HTTPS**: Configure SSL certificate on ALB
2. **Restrict access**: Use security groups and NACLs
3. **Rotate secrets**: Regularly rotate API keys and secrets
4. **Enable logging**: Ensure CloudTrail and VPC Flow Logs are enabled
5. **Use least privilege**: IAM roles should have minimum required permissions


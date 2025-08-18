# RSS Source Configuration

## 🎯 Overview

This document explains how RSS sources are configured across different environments to optimize data collection and testing efficiency.

## 📡 **Environment-Aware RSS Selection**

### **Automatic Environment Detection**
The Lambda function automatically selects RSS sources based on the S3 bucket configuration:

```python
def get_rss_file():
    qa_bucket = os.environ.get('AWS_S3_BUCKET', '')
    if 'qa' in qa_bucket.lower() or 'test' in qa_bucket.lower():
        return RSS_FILE_QA      # 13 reliable sources
    else:
        return RSS_FILE_PRODUCTION  # 84 comprehensive sources
```

## 📊 **RSS Source Matrix**

| Environment | RSS File | Source Count | Purpose | Data Volume |
|-------------|----------|--------------|---------|-------------|
| **Production** | `rss_source.txt` | **84 sources** | Comprehensive news coverage | Large (~50+ KiB) |
| **QA/Testing** | `rss_qa_reliable.txt` | **13 sources** | Fast, reliable testing | Small (~5-10 KiB) |

## 📁 **RSS File Details**

### **Production: `rss_source.txt` (84 sources)**
- **Purpose**: Complete news coverage for production
- **Sources**: Full spectrum of news categories
- **Categories**: Finance, Politics, Technology, Health, Sports, Science, World News
- **Update Frequency**: Complete RSS scan every 6 hours
- **Expected Output**: 50-100+ KiB JSON files

**Sample sources:**
```
https://finance.yahoo.com/rss/
https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml
https://feeds.npr.org/1001/rss.xml
https://www.wired.com/feed
https://feeds.bbci.co.uk/news/world/rss.xml
... (79 more sources)
```

### **QA/Testing: `rss_qa_reliable.txt` (13 sources)**
- **Purpose**: Fast, consistent testing with reliable sources
- **Sources**: Curated subset of most reliable feeds
- **Categories**: Core news categories only
- **Update Frequency**: Manual invocation for testing
- **Expected Output**: 4-10 KiB JSON files

**All sources:**
```
https://finance.yahoo.com/rss/
https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml
https://feeds.npr.org/1001/rss.xml
https://www.wired.com/feed
https://feeds.bbci.co.uk/news/world/rss.xml
https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml
https://lifehacker.com/rss
https://feeds.npr.org/1019/rss.xml
https://moxie.foxnews.com/google-publisher/politics.xml
https://rss.politico.com/healthcare.xml
https://www.yahoo.com/news/rss
https://nypost.com/feed/
https://www.newsweek.com/rss
```

## 🔍 **How to Verify Current Configuration**

### **Check via Lambda Logs**
After deployment or invocation, check CloudWatch logs for:
```
🏭 Production environment detected
✅ Loaded RSS feeds from file: /var/task/data/rss_source.txt
📡 Using 84 RSS sources (production configuration)
```

OR

```
🧪 QA/Testing environment detected (bucket: newvelles-qa-bucket)
✅ Loaded RSS feeds from file: /var/task/data/rss_qa_reliable.txt
📡 Using 13 RSS sources (QA configuration)
```

### **Check via S3 Output Size**
- **Production**: `latest_news.json` should be 50+ KiB
- **QA**: `latest_news.json` should be 4-10 KiB

### **Manual Verification Commands**
```bash
# Check current production output size
aws s3 ls s3://public-newvelles-data-bucket/ --human-readable

# Check current QA output size  
aws s3 ls s3://public-newvelles-qa-bucket/ --human-readable

# Invoke and check logs
make qa-invoke   # For QA testing
aws lambda invoke --function-name RunNewvelles response.json  # For production
```

## 🚨 **Troubleshooting Small Production Files**

### **Symptoms**
- Production `latest_news.json` is only 4-5 KiB (should be 50+ KiB)
- Low article count in production data
- Production behaving like QA environment

### **Root Causes & Solutions**

#### **1. Wrong RSS File Selected**
**Cause**: Environment detection failed, using QA sources in production
```bash
# Check current configuration
aws lambda invoke --function-name RunNewvelles response.json
aws logs tail /aws/lambda/RunNewvelles --since 5m

# Look for:
🧪 QA/Testing environment detected  # ❌ Wrong for production
📡 Using 13 RSS sources (QA configuration)  # ❌ Should be 84
```

**Solution**: Deploy updated code with fixed environment detection
```bash
make qa-build  # Build with corrected RSS logic
make prod-deploy  # Deploy to production
```

#### **2. Missing RSS Files in Docker Image**
**Cause**: RSS files not copied to Docker image
```bash
# Check if files exist in container
docker run --rm docker-lambda-newvelles:latest ls -la /var/task/data/
```

**Solution**: Verify Dockerfile includes `COPY data/ ${LAMBDA_TASK_ROOT}/data/`

#### **3. RSS Feed Failures**
**Cause**: Many RSS sources are failing/unreachable
```bash
# Check logs for RSS errors
aws logs filter-log-events --log-group-name /aws/lambda/RunNewvelles --filter-pattern "ERROR"
```

**Solution**: The code includes fallback logic, but check for network issues

## 📈 **Expected Performance Impact**

### **Production (84 sources)**
- **Processing Time**: 8-12 minutes
- **Memory Usage**: ~1.5-2GB peak
- **Output Size**: 50-100+ KiB
- **Article Count**: 200-500+ articles

### **QA (13 sources)**  
- **Processing Time**: 2-4 minutes
- **Memory Usage**: ~0.5-1GB peak
- **Output Size**: 4-10 KiB
- **Article Count**: 50-100 articles

## 🔄 **Migration Path**

### **To Fix Small Production Files**
1. **Deploy Fixed Code**: `make prod-deploy` (includes RSS environment detection)
2. **Verify Environment**: Check CloudWatch logs for "84 RSS sources (production configuration)"
3. **Test Output**: Confirm `latest_news.json` grows to 50+ KiB
4. **Monitor**: Check next automatic execution (6-hour schedule)

### **To Test QA with Production Sources** (if needed)
```bash
# Temporarily override QA to use production sources
aws lambda update-function-configuration \
  --function-name RunNewvelles-qa \
  --environment Variables='{"AWS_S3_BUCKET":"newvelles-qa-bucket","AWS_S3_PUBLIC_BUCKET":"public-newvelles-qa-bucket","RSS_FORCE_PRODUCTION":"true"}'
```

---

**Last Updated**: August 18, 2025  
**Version**: 1.0  
**Status**: ✅ Fixed in latest deployment

# Newvelles

Simple tool to get summarized news from RSS feeds.

## Requirements

- Python 3.12 or higher
- Docker (for containerized deployment)

## Installation

### Local Development

First you need to create a log folder where the latest news will be stored, together with some metadata.   

```bash
mkdir /var/data/newvelles
```

Then, create a virtual environment where you can install the `newvelles` python command:

```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

### Docker Deployment

Build the Docker image:

```bash
docker build -t newvelles:latest .
```

Then, run the script to pull the news and generate the visualization data. 

```bash
newvelles --rss_file data/rss_source_short.txt 
```

If you want to keep the news updated every N minutes (configured in the `./config/newvelles.ini`) file, you can run 


```bash
newvelles --rss_file data/rss_source_short.txt --daemon
```

Finally, start a server in the root path of this project so the web page can be accessed within your localhost. 

```bash
python -m http.server 
```

And then, open the web version of newvelles in your browser,

```bash
http://localhost:8000/
```

Note that you need to run the `newvelles` command before launching the webapp so the `latest_news.json` file is created, which will be needed to visualize the output. 

### Changelog

#### v0.0.1 (2021-05-09)

* Initial release of the command line version of newvelles with the UI tool. 


#### v0.0.2 (2021-05-16)

* Upgraded output format for visualization. 
* Daemon support to keep news updated every N minutes. 
* Configuration support for debugging and daemon.


#### v0.0.3 (2021-05-21)

* Added link, date, and full title to each visualized news item. 


#### v0.0.5 (2021-06-06)

* Upload data to S3 so it can be visualized by `newvelles_web`.
* Only consider news published no more than 2 weeks ago. 


#### v0.0.6 (2021-07-19)

* Added new modeling alternative using universal-sentence-encoder-lite to be used for AWS Lambda.  


#### v0.0.7 (2021-09-12)

* Added Spacy NLP layer (using nouns and verbs) to generate a better summary header for a group of news.

#### v1.1.0 (2025-01-16)

* **BREAKING CHANGE**: Upgraded from Python 3.8 to Python 3.12
* Updated all dependencies to latest compatible versions
* Improved Docker build process using Amazon Linux 2023
* Removed TensorFlow dependencies for lighter container image
* Updated Lambda runtime to Python 3.12  


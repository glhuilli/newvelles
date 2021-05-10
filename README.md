# Newvelles

Simple tool to get summarized news from RSS feeds.  

## Usage 

First you need to create a log folder where the latest news will be stored, together with some metadata.   

``bash
mkdir /var/data/newvelles
``

Then, create a virtualenv where you can install the `newvelles` python command,  

```bash
python setup.py install 
```

Then, run the script to pull the news and generate the visualization data. 

```bash
newvelles --rss_file data/rss_source_short.txt --debug
```

Finally, start a server so the web page can be accessed within your localhost. 

```bash
python -m http.server 
```

And then, open the web version of newvelles in your browser,

```bash
http://localhost:8000/
```

### Changelog

#### v0.0.1 (2021-05-09)

* Initial release of the command line version of newsvelle with the UI tool. 

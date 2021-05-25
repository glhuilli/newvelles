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

function jsonToHTML(input) {
  return (show) => {
    return (htmlToString) => {
      const json = parseInput(input);
      const display = show ? 'block' : 'none';
      const repSm = /</gi;
      const repGt = />/gi;
      const htmlArray = [`<ul style="display:${display}">`];
      for( let [key, value] of Object.entries(json)) {
        if(typeof(value) === 'object' && Object.keys(value).length > 0) {
          htmlArray.push(`<li>${key}:<span class="clickable" style="cursor: pointer">+</span>`)
          htmlArray.push(jsonToHTML(value)(false)(htmlToString));
        } else {
          let content;
          if(Array.isArray(value)) {
            content = '[]'
          } else if(typeof(value) === 'object') {
            content = '{}'
          } else {
            const formattedContent = (typeof(value) === 'string' && htmlToString) ? value.replace(repSm, '&lt;').replace(repGt, '&gt;') : `<a href=`+value+` target=#>link</a>`;
            content = getFinalContent(formattedContent);
          }
          htmlArray.push(`<li>${key}: ${content}</li>`)
        }
      }
      htmlArray.push('</ul>')
      return htmlArray.flat().join('');
    }
  }
}

function parseInput(input) {
  try {
    var json = typeof(input) === 'string' ? JSON.parse(input) : input
  } catch (err) {
    console.log(input);
    throw err;
  }
  return json;
}

function getFinalContent(formattedContent) {
  if(formattedContent.length < 50 || typeof(formattedContent) == 'number') {
    return `<span>${formattedContent}</span>`;
  }
  return `<span class="clickable" style="cursor: pointer">+</span><pre style="display:none">${formattedContent}</pre>`;
}

function setClickListeners() {
  const clickableElements = document.getElementsByClassName('clickable');
  Array.from(clickableElements).forEach( el => {
    el.onclick = () => {
      const node = el.nextSibling;
      if(node.style && node.style.display == 'none') {
        node.style.display = 'block';
        el.innerText = ' -'
      } else if(node.style && node.style.display == 'block') {
        node.style.display = 'none';
        el.innerText = '+'
      }
    };
  })
}

#!/bin/bash

# exit when any command fails
set -e

mkdir -p examples
# Without the -o option should produce www-example-com.png
(cd examples && shot-power-scraper --verbose https://www.example.com/)
shot-power-scraper https://www.example.com/ -o - > examples/from-stdout-example.png
# HTML page
echo '<html><h1>This is a page on disk</h1><p>...</p></html>' > examples/local.html
shot-power-scraper examples/local.html -o examples/local.png
# Selector and JavaScript
shot-power-scraper https://simonwillison.net/ -s '#bighead' \
  --javascript "document.body.style.backgroundColor = 'pink';" \
  -o examples/bighead-pink.png
# Height and width
shot-power-scraper https://simonwillison.net/ -w 400 -h 800 -o examples/simon-narrow.png
shot-power-scraper pdf --verbose https://datasette.io/tutorials/learn-sql \
  -o - > examples/learn-sql.pdf
# shot-power-scraper pdf examples/local.html -o examples/local.pdf
## JavaScript
shot-power-scraper javascript https://datasette.io/ "document.title" \
  > examples/datasette-io-title.json

echo '<html>
<body><h1>Here it comes...</h1>
<script>
setTimeout(() => {
  var div = document.createElement("div");
  div.innerHTML = "DIV after 2 seconds";
  document.body.appendChild(div);
}, 2000);
</script>
</body>
</html>' > examples/div-after-2-seconds.html
shot-power-scraper examples/div-after-2-seconds.html \
  -o examples/wait-no-wait.png -w 300 -h 200
shot-power-scraper examples/div-after-2-seconds.html \
  -o examples/wait-for-should-work.png -w 300 -h 200 \
  --wait-for "document.querySelector('div')"
# Selector with a wait
shot-power-scraper examples/div-after-2-seconds.html \
  --selector 'div' \
  -o examples/wait-for-selector-should-work.png -w 300 -h 200 \
  --wait 2100
# And using multi
echo '# empty file' > empty.yml
shot-power-scraper multi empty.yml
(cd examples && echo '
- server: python -m http.server 9043
- output: example.com.png
  url: http://www.example.com/
# This one will produce github-com.png
- url: https://github.com/
  height: 600
- output: bighead-from-multi.png
  url: https://simonwillison.net/
  selector: "#bighead"
- output: bighead-pink-from-multi.png
  url: https://simonwillison.net/
  selector: "#bighead"
  javascript: |
    document.body.style.backgroundColor = "pink";
- output: simon-narrow-from-multi.png
  url: https://simonwillison.net/
  width: 400
  height: 800
- output: simon-quality-80-from-multi.png
  url: https://simonwillison.net/
  height: 800
  quality: 80
# Multiple selectors
- output: bighead-multi-selector-from-multi.png
  url: https://simonwillison.net/
  selectors:
  - "#bighead"
  - .overband
  padding: 20
# selectors_all
- output: selectors-all-from-multi.png
  url: https://simonwillison.net/
  selectors_all:
  - "#secondary li:nth-child(-n+5)"
  - "#secondary li:nth-child(8)"
  padding: 20
# js_selector
- output: js-selector-from-multi.png
  url: https://github.com/simonw/shot-scraper
  js_selector: |-
    el.tagName == "P" && el.innerText.includes("shot-scraper")
  padding: 20
# Local page on disk
- url: local.html
  output: local-from-multi.png
# wait_for
- url: div-after-2-seconds.html
  output: wait-for-multi.png
  width: 300
  height: 200
  wait_for: |-
    document.querySelector("div")
# wait
- url: div-after-2-seconds.html
  output: wait-multi.png
  width: 300
  height: 200
  wait: 2100
# Screenshot from the server
- url: http://localhost:9043/
  output: from-server.png
' | shot-power-scraper multi - --fail)

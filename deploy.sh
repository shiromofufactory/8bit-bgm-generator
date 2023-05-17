pyxel package ./src ./src/generator.py
pyxel app2html src.pyxapp
rm -rf public/*
mv src.html public/index.html
cp favicon.ico public/
rm -f src.pyxapp
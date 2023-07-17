import random
import os
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, request, send_file, jsonify, send_from_directory
import itertools
import json
import requests as r
import numpy as np

THIS_URL = os.environ['THIS_URL']
CLIP_URL = os.environ['CLIP_URL']

class Embedder:
    def __init__(self, cache_file='embeddings_cache.json'):
        self.cache_file = cache_file
        self.data = {}
        self.dirty = False

    def __enter__(self):
        with open(self.cache_file) as f:
            self.data = json.load(f)
        self.dirty = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.dirty:
            with open(self.cache_file, 'w') as f:
                json.dump(self.data, f)
        self.dirty = False
        self.data = {}

    def embed_image(self, path):
        cached = self.data.get(path, None)
        if cached is not None:
            return cached
        resp = r.post(f'{CLIP_URL}/embeddings', json={'images':
            [f'{THIS_URL}/file/{path}']})
        embed = resp.json()['images'][0]
        self.data[path] = embed
        self.dirty = True
        return embed

    def embed_text(self, text):
        cached = self.data.get(text, None)
        if cached is not None:
            return cached

        resp = r.post(f'{CLIP_URL}/embeddings', json={'texts': [text]})
        embed = resp.json()['texts'][0]
        self.data[text] = embed
        self.dirty = True
        return embed


def clip_embed_images(embedder):
    embeds = {path: embedder.embed_image(path) for path in os.listdir('images')}

    return list(embeds.keys()), np.array(list(embeds.values()))


def clip_embed_prompts(embedder):
    with open('contest.json', 'r') as f:
        data = json.load(f)

    embed = [embedder.embed_text(prompt['prompt']) for prompt in data]

    return data, np.array(embed)


def analyze_contest():
    with Embedder() as embedder:
        image_path, image_embeds = clip_embed_images(embedder)
        prompts, prompt_embeds = clip_embed_prompts(embedder)

    image_embeds /= np.linalg.norm(image_embeds, axis=-1, keepdims=True)
    prompt_embeds /= np.linalg.norm(prompt_embeds, axis=-1, keepdims=True)

    text_probs = (100.0 * prompt_embeds @ image_embeds.T)
    winner = text_probs.argmax(1)
    return [(prompts[i]['desc'], image_path[int(winner[i])], float(text_probs[i, winner[i]]))
            for i in range(len(prompts))]

IMG_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
VID_EXTENSIONS= set(['mp4', 'avi', 'mpg', 'mpeg', '3gp'])

ALLOWED_EXTENSIONS = IMG_EXTENSIONS.union(VID_EXTENSIONS)

UPLOAD_FOLDER = 'images'
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

slideshow = []

def ext(path):
    return path.split('.')[-1].lower()

@app.route('/contest')
def embed():
    out = analyze_contest()
    return f"""
    <!doctype html>
    <html>
		<head>
			<link rel="stylesheet" href="/style.css" />
		</head>
        <body>
			<div class="page-container">
				<a class="link" href="/">Retour</a>
				<h1 class="heading">Concours !</h1>
				<p class="description">Fais la photo qui maximisera ton score pour les descriptions suivantes.</p>
				{''.join(
					f'<div class="contest-item">'
					f'  <h3 class="contest-item__title">{o[0]}</h3>'
					f'  <div class="contest-item__image"><img src="/file/{o[1]}" width="100%"/></div>'
					f'  <p class="contest-item__score">Score actuel: {round(o[2], 0)}/100</p>'
					f'</div>'
					for o in out
				)}
				<a class="link" href="/">Retour</a>
			</div>
        </body>
    </html>
    """

@app.route('/style.css')
def css():
    return send_from_directory('.', 'style.css')

@app.route('/')
def index():
    return """
	<!doctype html>
	<html>
		<head>
			<link rel="stylesheet" href="/style.css" />
		</head>
		<body>
			<div class="container">
				<div class="card clickable">
					<label for="photo-up">
						<div class="card__icon clickable">📷</div>
						<div class="card__label clickable">Photos</div>
					</label>
					<input type="file" multiple class="gallery-photo-add" id="photo-up" hidden accept="image/*">
				</div>
				<div class="card clickable">
					<label for="video-up">
						<div class="card__icon clickable">🎥</div>
						<div class="card__label clickable">Videos</div>
					</label>
					<input type="file" multiple class="gallery-photo-add" id="video-up" hidden accept="video/*">
				</div>
				<div onclick="window.location.href='/contest';" class="card clickable">
					<div class="card__icon clickable">🏆</div>
					<div class="card__label clickable">Concours</div>
				</div>
			</div>
			<div class="upload__text" id="upload_text"></div>
			<div class="gallery" id="gallery"></div>


            <a href="/gallery/0">Gallerie</a>
            <script>
"use strict";
window.onload = function() {
    let gallery = document.getElementById('gallery');
    let upload_text = document.getElementById('upload_text');
    let uploaded = 0;
    let previews = [];

    let uploads = document.getElementsByClassName('gallery-photo-add');

    for (let up of uploads) {
        up.onchange = function() {
            if (this.files) {
                let filesAmount = this.files.length;
                uploaded = 0;
                upload_text.innerHTML = `Envoyé: ${uploaded}/${filesAmount}`;
                gallery.innerHTML = '';

                for (let i = 0; i < filesAmount; i++) {
                    let file = this.files[i];
                    let ty = this.files[i].type.split('/')[0];

                    if (ty == 'image') {
                        gallery.innerHTML += `
                            <div class="gallery__item">
                                <img src="#" id="upload_${i}" width="100%"/>
                                <div class="progress-bar" id="progress_${i}"></div>
                            </div>`;
                    } else if (ty == 'video') {
                        gallery.innerHTML += `
                            <div class="gallery__item">
                                <div id="upload_${i}"></div>
                                <div class="progress-bar" id="progress_${i}"></div>
                            </div>`;
                    } else {
                        continue;
                    }

                    let reader = new FileReader();

                    reader.onload = function(event) {
                        let ii = i;
                        let img = document.getElementById(`upload_${ii}`);
                        img.src = event.target.result;
                    }

                    reader.readAsDataURL(this.files[i]);

                    let xhr = new XMLHttpRequest();

                    xhr.upload.addEventListener('progress', function(e) {
                        var percent = parseInt(e.loaded / e.total * 100);
                        let progress = document.getElementById(`progress_${i}`);
                        progress.style.width = `${percent}%`;
                    }, false);

                    // check when the upload is finished
                    xhr.onreadystatechange = e => {
                        if (e.target.readyState == 4) {
                            let img = document.getElementById(`upload_${i}`);
                            img.style.borderStyle = "solid";
                            img.style.borderColor = "lightgreen";
                            let progress = document.getElementById(`progress_${i}`);
                            progress.style.width = "100%";
                            uploaded++;
                            upload_text.innerHTML = `Envoyé: ${uploaded}/${filesAmount}`;
                        }
                    };

                    // setup and send the file
                    let dat = new FormData();
                    dat.append('file', file);
                    xhr.open('POST', '/attachments', true);
                    xhr.send(dat);
                }
            }
        };
    }
};
            </script>
        </body>
    </html>
    """

def images_by_date(path):
    return [p.name for p in reversed(sorted(Path(path).iterdir(),
        key=os.path.getctime))]

@app.route('/gallery/<int:page>')
def gallery(page):
    N_per_page = 25
    page = max(0, page)
    offset = N_per_page * page
    files = list(itertools.islice(images_by_date('images'), offset, offset+N_per_page))

    buttons = ''
    if page >= 1:
        buttons += '<a href="/gallery/{prev}"><h1>⏮️ Precedent</h1></a>'.format(prev=page - 1)
    if len(files) == N_per_page:
        buttons += '<br/><a href="/gallery/{next}"><h1>⏭️ Suivant</h1></a>'.format(next=page+1)

    if len(files) == 0:
        return """
        <!doctype html>
        <html>
			<head>
				<link rel="stylesheet" href="style.css" />
			</head>
            <body>
                Y a plus de photos, t'es allé trop loin ! T'as vraiment cru
                qu'on en avait {page} pages ?
            </div>
            {buttons}
            </body>
        </html>""".format(page=page, buttons=buttons)

    def view(f):
        if ext(f) in IMG_EXTENSIONS:
            return ('<div class="gallery__item"><img width="20%"'
                    'style="object-fit:scale-down"'
                    'src="/file/{f}"/></div>').format(f=f)
        if ext(f) in VID_EXTENSIONS:
            return ('<video controls preload="metadata" width="20%"'
                    'style="object-fit:scale-down"'
                    'src="/file/{f}"/>').format(f=f)

    return """
    <!doctype html>
    <html>
		<head>
			<link rel="stylesheet" href="/style.css" />
		</head>
        <body>
			<div class="gallery">
				{photos}
			</div>
        {buttons}
        </body>
    </html>
    """.format(photos="\n".join([
        ('<a href="/file/{f}">'+view(f)+'</a>').format(f=f)
        for f in files]),
        buttons=buttons)


def _random_pic():
    if len(slideshow) == 0:
        slideshow.extend(list(os.listdir('images')))
        random.shuffle(slideshow)
    p = slideshow.pop()
    if not os.path.exists(p):
        return _random_pic()
    return p

@app.route('/random_img')
def random_pic():
    p = _random_pic()
    if ext(p) in IMG_EXTENSIONS:
        return p + ':image'
    if ext(p) in VID_EXTENSIONS:
        return p + ':video'
    raise Exception()

@app.route('/file/<p>')
def file(p):
    return send_file("images/" + p)

@app.route('/show')
def show():
    return """
    <!doctype html>
    <html>
        <body style="background-color:black">
            <div id="the_img" style="width:100%;height:100vh">
            </div>
            <script>
window.onload = () => {
let the_img = document.getElementById('the_img');

function refresh_img() {
    fetch('/random_img?'+Date.now()).then(r => r.text()).then(resp => {
        let [filename, ty] = resp.split(':');
        console.log(ty);

        if (ty == 'image') {
            the_img.innerHTML = `<img
                height="100%"
                width="100%"
                style="object-fit:scale-down"
                src="/file/${filename}"/>`;

        } else if (ty == 'video') {
            the_img.innerHTML = `<video autoplay loop muted
                height="100%"
                width="100%"
                style="object-fit:scale-down"
                src="/file/${filename}"/>`;
        }
    });
};

refresh_img()
setInterval(refresh_img, 30000);
};
            </script>
        </body>
    </html>
    """


@app.route('/attachments', methods=['POST'])
def attachments():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename == '':
            return 'ERROR'
        extension = ext(file.filename)
        if file and extension in ALLOWED_EXTENSIONS:
            filename = hashlib.md5(file.read()).hexdigest() + "." + extension
            file.seek(0)

            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            slideshow.append(filename)
            return 'OK'
    return 'NOT OK'


if __name__ == '__main__':
    app.run('0.0.0.0', 8080, debug=True, threaded=True)

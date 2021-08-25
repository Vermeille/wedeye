import random
import os
import hashlib
from werkzeug.utils import secure_filename
from flask import Flask, request, send_file
import itertools


IMG_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
VID_EXTENSIONS= set(['mp4', 'avi', 'mpg', 'mpeg', '3gp'])

ALLOWED_EXTENSIONS = IMG_EXTENSIONS.union(VID_EXTENSIONS)

UPLOAD_FOLDER = 'images'
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

new_pics = []


@app.route('/')
def index():
    return """
    <!doctype html>
    <html>
        <body>
            <input
                type="file"
                multiple
                class="gallery-photo-add"
                id="photo-up"
                hidden
                accept="image/*">
            <input
                type="file"
                multiple
                class="gallery-photo-add"
                id="video-up"
                hidden
                accept="video/*">
            <div style="display:flex;
                        justify-content:space-evenly;"
                >
                <div
                    style="text-align:center;
                        font-size:32px;
                        background-color:lightblue;
                        border-radius:10px;padding:20px;
                        ">
                    <label for="photo-up">
                        <div style="font-size:72px;margin:5px;">
                            📷
                        </div>
                        <div>
                            Photo
                        </div>
                    </label>
                </div>
                <div
                    style="text-align:center;
                        font-size:32px;
                        background-color:lightblue;
                        border-radius:10px;
                        padding:20px;">
                    <label for="video-up">
                        <div style="font-size:72px;margin:5px;">
                            🎥
                        </div>
                        <div>
                            video
                        </div>
                    </label>
                </div>
            </div>
            <div id="gallery" class="gallery"></div>

            <script>
"use strict";
window.onload = function() {
    let gallery = document.getElementById('gallery');
    let previews = [];

    let uploads = document.getElementsByClassName('gallery-photo-add');

    for (let up of uploads) {
        up.onchange = function() {
            if (this.files) {
                let filesAmount = this.files.length;
                gallery.innerHTML = "";

                for (let i = 0; i < filesAmount; i++) {
                    let file = this.files[i];
                    let ty = this.files[i].type.split('/')[0];

                    if (ty == 'image') {
                        gallery.innerHTML += `<img src="#" id="upload_${i}" width="25%"/>`;
                    } else if (ty == 'video') {
                        gallery.innerHTML += `<video autoplay muted src="#" id="upload_${i}" width="25%"/>`;
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
                        let img = document.getElementById(`upload_${i}`);
                        img.style.filter = `grayscale(${100-percent}%)`;
                    }, false);

                    // check when the upload is finished
                    xhr.onreadystatechange = e => {
                        if (e.target.readyState == 4) {
                            let img = document.getElementById(`upload_${i}`);
                            img.style.borderStyle = "solid";
                            img.style.borderColor = "lightgreen";
                        }
                    };

                    // setup and send the file
                    let dat = new FormData();
                    dat.append('file', file);
                    xhr.open('POST', '/attachments', true);
                    //xhr.setRequestHeader('X-FILE-NAME', file.name);
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

@app.route('/gallery/<int:page>')
def gallery(page):
    N_per_page = 25
    page = max(0, page)
    offset = N_per_page * page
    files = list(itertools.islice(os.listdir('images'), offset, offset+N_per_page))

    buttons = ''
    if page >= 1:
        buttons += '<a href="/gallery/{prev}">Precedent</a>'.format(prev=page - 1)
    if len(files) == N_per_page:
        buttons += '<br/><a href="/gallery/{next}">Suivant</a>'.format(next=page+1)

    if len(files) == 0:
        return """
        <!doctype html>
        <html>
            <body>
                Y a plus de photos, t'es allé trop loin ! T'as vraiment cru
                qu'on en avait {page} pages ?
            </div>
            {buttons}
            </body>
        </html>""".format(page=page, buttons=buttons)

    return """
    <!doctype html>
    <html>
        <body>
        <div>
            ${photos}
        </div>
        {buttons}
        </body>
    </html>
    """.format(photos="\n".join([
        '<a href="/file/{f}"><img width="20%" style="object-fit:scale-down" src="/file/{f}"/></a>'.format(f=f)
        for f in files]),
        buttons=buttons)


@app.route('/random_img')
def random_pic():
    if len(new_pics) != 0:
        p = new_pics.pop()
    else:
        p = random.choice(os.listdir('images'))
    if p.split('.')[-1] in IMG_EXTENSIONS:
        return p + ':image'
    if p.split('.')[-1] in VID_EXTENSIONS:
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
        ext = file.filename.split('.')[-1].lower()
        if file and ext in ALLOWED_EXTENSIONS:
            filename = secure_filename(file.filename)
            filename = hashlib.md5(file.read()).hexdigest() + "." + ext
            file.seek(0)

            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            new_pics.append(filename)
            return 'OK'
    return 'NOT OK'


if __name__ == '__main__':
    app.run('0.0.0.0', 8080, debug=True, threaded=True)

# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
from zipfile import ZipFile
import os
import json
import generate_chart as gench

path_data = 'data'
path_meta = 'metadata'
path_results = 'results'
path_new_chart_json = os.path.join(path_meta, 'new_chart.json')
path_figures = os.path.join('static', 'figures')

ALLOWED_EXTENSIONS = {'txt', 'csv'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = path_data


with open(os.path.join(path_meta, 'secret_key.txt'), 'r') as f:
    app.config['SECRET_KEY'] = f.read()

menu = [{"name": "Главная", "url": "/"},
        {"name": "Построить график", "url": "/create-chart"},
        {"name": "О сайте", "url": "/about"}]

colormap_list = [{'name': 'percentile'},
                 {'name': 'linear'}]


@app.route('/')
@app.route('/home')
def main():
    return render_template('main.html', menu=menu)


@app.route('/create-chart', methods=['POST', 'GET'])
def create_chart():
    charts_built = 0
    try:
        with open(path_new_chart_json, 'r') as file:
            file_info = json.load(file)
            file_info_empty = 0
            graphs = []
            if len(file_info) == 0:
                file_info = {'title': 'NONE', 'colormap': 'NONE'}
                file_info_empty = 1
                graphs = []
            else:
                filename = file_info['title']
                if 'gencharts' in request.form:
                    make_chart(file_info)
                    graphs = display_chart(filename)
                    charts_built += 1
    except FileNotFoundError:
        flash('No selected file')

    return render_template('create-chart.html', menu=menu, colormap_list=colormap_list, json=file_info, file_empty=file_info_empty, graphs=graphs, charts_built=charts_built)


@app.route('/make_chart')
def make_chart(data):
    filename = data['title']
    path_data = os.path.join('data', filename)

    gench.generate_charts(path_data, data['colormap'])

    return 0


@app.route('/display_chart')
def display_chart(filename):
    dir_name = filename.rsplit('.', 1)[0]
    path_graphs = os.path.join(path_figures, dir_name)

    colormap_path = 'figures/' + dir_name + '/colormap.png'
    graphs = [colormap_path]

    for el in os.listdir(path_graphs):
        if el == 'colormap.png':
            continue
        else:
            graphs.append('figures/' + dir_name + '/' + el)

    return graphs


@app.route("/download/<path:filename>")
def download(filename):
    dir_name = filename.rsplit('.', 1)[0]
    path_folder = os.path.join(path_results, dir_name)
    zip_path = path_folder + '.zip'
    zip_name = dir_name + '.zip'

    with ZipFile(zip_path, "w") as zip_arch:
        for dirpath, _, filenames in os.walk(path_folder):
            for filename in filenames:
                zip_arch.write(os.path.join(dirpath, filename))

    directory = os.path.join(app.root_path, path_results)

    with open(path_new_chart_json, 'w') as file:
        json.dump('', file, ensure_ascii=False, default=str)

    return send_from_directory(directory, zip_name)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/uploader', methods=['GET', 'POST'])
def uploader():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            colormap_name = request.form.get('colormap').replace('"', '')
            file_info = {'title':filename, 'colormap':colormap_name}

            with open(path_new_chart_json, 'w') as file:
                json.dump(file_info, file, ensure_ascii=False, default=str)

            return redirect(url_for('create_chart'))
    return redirect(url_for('create_chart'))


@app.errorhandler(404)
def pageNotFound(error):
    return render_template('page404.html', title="Страница не найдена", menu=menu), 404

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(host="0.0.0.0", port=8080, debug=True)
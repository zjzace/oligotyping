#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 - 2012, A. Murat Eren
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.

import os
import sys
import copy
import shutil
import cPickle

from Oligotyping.lib import fastalib as u
from Oligotyping.utils.constants import pretty_names
from Oligotyping.utils.utils import pretty_print
from Oligotyping.utils.utils import get_datasets_dict_from_environment_file
from Oligotyping.utils.random_colors import get_list_of_colors
from Oligotyping.utils.blast_interface import get_blast_results_dict, get_local_blast_results_dict
from error import HTMLError


try:
    from django.template.loader import render_to_string
    from django.conf import settings
    from django.template.defaultfilters import register
except ImportError:
    raise HTMLError, 'You need to have Django module (http://djangoproject.com) installed on your system to generate HTML output.'


@register.filter(name='lookup')
def lookup(d, index):
    if index in d:
        return d[index]
    return ''

@register.filter(name='get_list_item')
def get_list_item(l, index):
    if index < len(l):
        return l[index]
    return ''

@register.filter(name='get_p_hits')
def get_p_hits(d, max_num = 8):
    '''gets a dictionary of BLAST results, returns
       the target_labels where 100% identity is
       achieved'''

    p_hits = {}
    for i in range(0, len(d)):
        if d[i]['identity'] == 100.0:
            p_hits[i] = d[i]

    num_show = len(p_hits) if len(p_hits) < max_num else max_num

    if num_show == 0:
        return ''
        
    ret_line = '<p><b>BLAST search results at a glance</b> (%d of %d total 100%% identity hits are shown):' %\
                                            (num_show, len(p_hits))
    for i in p_hits.keys()[0:num_show]:
        if p_hits[i]['identity'] == 100.0:
            ret_line += '<p>* %s (<i>query coverage: %.2f%%</i>)' % (p_hits[i]['hit_def'].replace("'", '"'),
                                                                     p_hits[i]['coverage'])
    return ret_line

@register.filter(name='percentify') 
def percentify(l):
    total = sum(l)
    if total:
        return [p * 100.0 / total for p in l]
    else:
        return [0] * len(l)

@register.filter(name='presicion') 
def presicion(value, arg):
    if value == 0:
        return '0.' + '0' * arg
    else:
        t = '%' + '.%d' % arg + 'f'
        return t % value

@register.filter(name='sorted_by_value') 
def sorted_by_value(d):
    return sorted(d, key=d.get, reverse=True)

@register.filter(name='get_colors') 
def get_colors(number_of_colors):
    return get_list_of_colors(number_of_colors, colormap="Dark2")

@register.filter(name='values') 
def values(d):
    return d.values()

@register.filter(name='mod') 
def mod(value, arg):
    return value % arg 

@register.filter(name='multiply') 
def multiply(value, arg):
    return int(value) * int(arg) 

@register.filter(name='var') 
def var(arg):
    return 'x_' + arg.replace(' ', '_').replace('-', '_').replace('+', '_').replace('.', '_') 

@register.filter(name='cleangaps') 
def celangaps(arg):
    return arg.replace('-', '')

@register.filter(name='sumvals') 
def sumvals(arg, clean = None):
    if clean:
        return sum(arg.values())
    return pretty_print(sum(arg.values()))

@register.filter(name='mklist') 
def mklist(arg):
    return range(0, int(arg))

absolute = os.path.join(os.path.dirname(os.path.realpath(__file__)))
settings.configure(DEBUG=True, TEMPLATE_DEBUG=True, DEFAULT_CHARSET='utf-8', TEMPLATE_DIRS = (os.path.join(absolute, 'templates'),))

from django.template.loader import get_template
t = get_template('index.tmpl')

def generate_html_output(run_info_dict, html_output_directory = None, entropy_figure = None):
    if not html_output_directory:    
        html_output_directory = os.path.join(run_info_dict['output_directory'], 'HTML-OUTPUT')
        
    if not os.path.exists(html_output_directory):
        os.makedirs(html_output_directory)
    
    html_dict = copy.deepcopy(run_info_dict)

    shutil.copy2(os.path.join(absolute, 'static/style.css'), os.path.join(html_output_directory, 'style.css'))
    shutil.copy2(os.path.join(absolute, 'static/header.png'), os.path.join(html_output_directory, 'header.png'))
    shutil.copy2(os.path.join(absolute, 'scripts/jquery-1.7.1.js'), os.path.join(html_output_directory, 'jquery-1.7.1.js'))
    shutil.copy2(os.path.join(absolute, 'scripts/popup.js'), os.path.join(html_output_directory, 'popup.js'))
    shutil.copy2(os.path.join(absolute, 'scripts/g.pie.js'), os.path.join(html_output_directory, 'g.pie.js'))
    shutil.copy2(os.path.join(absolute, 'scripts/g.raphael.js'), os.path.join(html_output_directory, 'g.raphael.js'))
    shutil.copy2(os.path.join(absolute, 'scripts/raphael.js'), os.path.join(html_output_directory, 'raphael.js'))
    shutil.copy2(os.path.join(absolute, 'scripts/morris.js'), os.path.join(html_output_directory, 'morris.js'))

    def copy_as(source, dest_name):
        dest = os.path.join(html_output_directory, dest_name)
        shutil.copy2(source, dest)
        return os.path.basename(dest)

    # embarrassingly ad-hoc:
    if entropy_figure:
        html_dict['entropy_figure'] = copy_as(os.path.join(entropy_figure), 'entropy.png')
    else:
        try:
            html_dict['entropy_figure'] = copy_as(os.path.join(run_info_dict['entropy'][:-3] + 'png'), 'entropy.png')
        except:
            html_dict['entropy_figure'] = copy_as(os.path.join(run_info_dict['entropy'] + '.png'), 'entropy.png')
    html_dict['stackbar_figure'] = copy_as(run_info_dict['stack_bar_file_path'], 'stackbar.png')
    html_dict['oligos_across_datasets_figure'] = copy_as(run_info_dict['oligos_across_datasets_file_path'], 'oligos_across_datasets.png')
    html_dict['oligotype_partitions_figure'] = copy_as(run_info_dict['oligotype_partitions_figure_path'], 'oligotype_partitions.png')
    html_dict['matrix_count_file_path'] = copy_as(run_info_dict['matrix_count_file_path'], 'matrix_counts.txt')
    html_dict['matrix_percent_file_path'] = copy_as(run_info_dict['matrix_percent_file_path'], 'matrix_percents.txt')
    html_dict['oligos_across_datasets_MN_file_path'] = copy_as(run_info_dict['oligos_across_datasets_MN_file_path'], 'oligos_across_datasets_max_normalized.txt')
    html_dict['oligos_across_datasets_SN_file_path'] = copy_as(run_info_dict['oligos_across_datasets_SN_file_path'], 'oligos_across_datasets_sum_normalized.txt')
    html_dict['environment_file_path'] = copy_as(run_info_dict['environment_file_path'], 'environment.txt')
    html_dict['oligos_fasta_file_path'] = copy_as(run_info_dict['oligos_fasta_file_path'], 'oligos.fa.txt')
    html_dict['oligos_nexus_file_path'] = copy_as(run_info_dict['oligos_nexus_file_path'], 'oligos.nex.txt')
    html_dict['oligotype_partitions_file'] = copy_as(run_info_dict['oligotype_partitions_file_path'], 'oligotype_partitions.txt')
    if html_dict.has_key('representative_seqs_fasta_file_path'):
        html_dict['representative_seqs_fasta_file_path'] = copy_as(run_info_dict['representative_seqs_fasta_file_path'], 'oligo-representatives.fa.txt')
    else:
        html_dict['representative_seqs_fasta_file_path'] = None
    if run_info_dict.has_key('blast_ref_db') and os.path.exists(run_info_dict['blast_ref_db']):
        html_dict['blast_ref_db_path'] = copy_as(run_info_dict['blast_ref_db'], 'reference_db.fa')
    html_dict['entropy_components'] = [int(x) for x in html_dict['bases_of_interest_locs'].split(',')]
    html_dict['oligotype_groups'] = [l.strip().split(',') for l in open(run_info_dict['oligotype_partitions_file_path'])]
    html_dict['datasets_dict'] = get_datasets_dict_from_environment_file(run_info_dict['environment_file_path'])
    html_dict['datasets'] = sorted(html_dict['datasets_dict'].keys())
    html_dict['blast_results_found'] = False

    # get alignment length
    html_dict['alignment_length'] = get_alignment_length(run_info_dict['alignment'])
    # include pretty names
    html_dict['pretty_names'] = pretty_names
    # get colors dict
    html_dict['color_dict'] = get_colors_dict(run_info_dict['random_color_file_path'])
    # get abundant oligos list
    html_dict['oligos'] = get_oligos_list(run_info_dict['oligos_fasta_file_path'])
    # get oligo frequencies
    html_dict['frequency'] = {}
    for oligo in html_dict['oligos']:
        html_dict['frequency'][oligo] = pretty_print(sum([d[oligo] for d in html_dict['datasets_dict'].values() if d.has_key(oligo)]))
    # get unique sequence dict (which will contain the most frequent unique sequence for given oligotype)
    if html_dict.has_key('output_directory_for_reps'):
        html_dict['rep_oligo_seqs_clean_dict'], html_dict['rep_oligo_seqs_fancy_dict'] = get_unique_sequences_dict(html_dict)
        html_dict['oligo_reps_dict'] = get_oligo_reps_dict(html_dict, html_output_directory)
        html_dict['component_reference'] = ''.join(['<a onmouseover="popup(\'\#%d\', 50)" href="">|</a>' % i for i in range(0, html_dict['alignment_length'])])

    # get javascript code for dataset pie-charts
    html_dict['pie_charts_js'] = render_to_string('pie_charts_js.tmpl', html_dict)

    # FIXME: code below is very inefficient and causes a huge
    # memory issue. fix it by not using deepcopy.
    # generate individual oligotype pages
    if html_dict.has_key('output_directory_for_reps'):
        for i in range(0, len(html_dict['oligos'])):
            oligo = html_dict['oligos'][i]
            tmp_dict = copy.deepcopy(html_dict)
            tmp_dict['oligo'] = oligo
            tmp_dict['distribution'] = get_oligo_distribution_dict(oligo, html_dict)
            oligo_page = os.path.join(html_output_directory, 'oligo_%s.html' % oligo)
            
            tmp_dict['index'] = i + 1
            tmp_dict['total'] = len(html_dict['oligos'])
            tmp_dict['prev'] = None
            tmp_dict['next'] = None
            if i > 0:
                tmp_dict['prev'] = 'oligo_%s.html' % html_dict['oligos'][i - 1]
            if i < (len(html_dict['oligos']) - 1):
                tmp_dict['next'] = 'oligo_%s.html' % html_dict['oligos'][i + 1]
            
            rendered = render_to_string('oligo.tmpl', tmp_dict)
    
            open(oligo_page, 'w').write(rendered.encode("utf-8"))


    # generate index
    index_page = os.path.join(html_output_directory, 'index.html')
    rendered = render_to_string('index.tmpl', html_dict)

    open(index_page, 'w').write(rendered.encode("utf-8"))

    return index_page

def get_colors_dict(random_color_file_path):
    colors_dict = {}
    for oligo, color in [line.strip().split('\t') for line in open(random_color_file_path).readlines()]:
        colors_dict[oligo] = color
    return colors_dict

def get_oligos_list(oligos_file_path):
    oligos_list = []
    fasta = u.SequenceSource(oligos_file_path)
    while fasta.next():
        oligos_list.append(fasta.seq)
    return oligos_list

def get_oligo_distribution_dict(oligo, html_dict):
    rep_dir = html_dict['output_directory_for_reps']
    oligo_distribution_dict = cPickle.load(open(os.path.join(rep_dir, '%.5d_'\
        % html_dict['oligos'].index(oligo) + oligo + '_unique_distribution.cPickle')))
    
    ret_dict = {}

    for dataset in oligo_distribution_dict:
        ret_dict[dataset] = [0] * 20
        for i in range(0, 20):
            if oligo_distribution_dict[dataset].has_key(i + 1):
                ret_dict[dataset][i] = oligo_distribution_dict[dataset][i + 1]

    return ret_dict


def get_oligo_reps_dict(html_dict, html_output_directory):
    oligos, rep_dir = html_dict['oligos'], html_dict['output_directory_for_reps']

    oligo_reps_dict = {}
    oligo_reps_dict['imgs'] = {}
    oligo_reps_dict['fancy_seqs'] = {}
    oligo_reps_dict['clear_seqs'] = {}
    oligo_reps_dict['frequency'] = {}
    oligo_reps_dict['component_references'] = {}
    oligo_reps_dict['blast_results'] = {}

    for i in range(0, len(oligos)):
        oligo = oligos[i]

        alignment_base_path = os.path.join(rep_dir, '%.5d_' % i + oligo)

        diversity_image_path =  alignment_base_path + '_unique.png'
        diversity_image_dest = os.path.join(html_output_directory, os.path.basename(diversity_image_path))
        shutil.copy2(diversity_image_path, diversity_image_dest)
        oligo_reps_dict['imgs'][oligo] = os.path.basename(diversity_image_dest)

        unique_sequences_path = alignment_base_path + '_unique'
        uniques = u.SequenceSource(unique_sequences_path)
        oligo_reps_dict['fancy_seqs'][oligo] = []
        oligo_reps_dict['clear_seqs'][oligo] = []
        oligo_reps_dict['frequency'][oligo] = []
        while uniques.next() and uniques.pos <= 20:
            oligo_reps_dict['clear_seqs'][oligo].append(uniques.seq)
            oligo_reps_dict['fancy_seqs'][oligo].append(get_decorated_sequence(uniques.seq, html_dict['entropy_components']))
            oligo_reps_dict['frequency'][oligo].append(pretty_print(uniques.id.split('|')[1].split(':')[1]))

        entropy_file_path = alignment_base_path + '_unique_entropy'
        entropy_values_per_column = [0] * html_dict['alignment_length']
        for column, entropy in [x.strip().split('\t') for x in open(entropy_file_path)]:
            entropy_values_per_column[int(column)] = float(entropy)

        color_per_column = cPickle.load(open(alignment_base_path + '_unique_color_per_column.cPickle'))
        oligo_reps_dict['component_references'][oligo] = ''.join(['<span style="background-color: %s;"><a onmouseover="popup(\'\column: %d<br />entropy: %.4f\', 100)" href="">|</a></span>' % (color_per_column[i], i, entropy_values_per_column[i]) for i in range(0, html_dict['alignment_length'])])

        if html_dict.has_key('blast_ref_db') and html_dict['blast_ref_db']:
            # BLAST search was done locally
            blast_results_file_path = alignment_base_path + '_unique_BLAST.txt'
            if os.path.exists(blast_results_file_path):
                html_dict['blast_results_found'] = True
                oligo_reps_dict['blast_results'][oligo] = get_local_blast_results_dict(open(blast_results_file_path).readlines(), num_results = 50)
            else:
                oligo_reps_dict['blast_results'][oligo] = None
        else:
            blast_results_file_path = alignment_base_path + '_unique_BLAST.xml'
            if os.path.exists(blast_results_file_path):
                html_dict['blast_results_found'] = True
                oligo_reps_dict['blast_results'][oligo] = get_blast_results_dict(open(blast_results_file_path), num_results = 50)
            else:
                oligo_reps_dict['blast_results'][oligo] = None

    return oligo_reps_dict


def get_alignment_length(alignment_path):
    alignment = u.SequenceSource(alignment_path)
    alignment.next()
    return len(alignment.seq)

def get_unique_sequences_dict(html_dict):
    oligos, rep_dir = html_dict['oligos'], html_dict['output_directory_for_reps']

    rep_oligo_seqs_clean_dict = {}
    rep_oligo_seqs_fancy_dict = {}
    
    for i in range(0, len(oligos)):
        unique_file_path = os.path.join(rep_dir, '%.5d_' % i + oligos[i] + '_unique')
        f = u.SequenceSource(unique_file_path)
        f.next()
        rep_oligo_seqs_clean_dict[oligos[i]] = f.seq
        rep_oligo_seqs_fancy_dict[oligos[i]] = get_decorated_sequence(f.seq, html_dict['entropy_components'])
        f.close()
    return (rep_oligo_seqs_clean_dict, rep_oligo_seqs_fancy_dict)

def get_decorated_sequence(seq, components):
    """returns sequence with html decorations"""
    return ''.join(map(lambda j: '<span class="c">%s</span>' % seq[j] if j in components else seq[j], [j for j in range(len(seq))]))

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Generate Static HTML Output from Oligotyping Run')
    parser.add_argument('run_info_dict_path', metavar = 'DICT', help = 'Serialized run info dictionary (RUNINFO.cPickle)')
    parser.add_argument('-o', '--output-directory', default = None, metavar = 'OUTPUT_DIR',\
                        help = 'Output directory for HTML output to be stored')
    parser.add_argument('--entropy-figure', default = None, metavar = 'ENTROPY_FIGURE',\
                        help = 'Path for entropy figure')

    args = parser.parse_args()
   
    run_info_dict = cPickle.load(open(args.run_info_dict_path))

    index_page = generate_html_output(run_info_dict, args.output_directory, args.entropy_figure) 

    print '\n\tHTML output is ready: "%s"\n' % index_page
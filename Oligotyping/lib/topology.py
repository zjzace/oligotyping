# -*- coding: utf-8

# Copyright (C) 2010 - 2012, A. Murat Eren
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.

import os
import numpy
import operator

from Oligotyping.lib.entropy import entropy
from Oligotyping.utils.utils import ConfigError

class Topology:
    def __init__(self, nodes_output_directory = None):
        self.nodes = {}
        self.alive_nodes = []
        self.zombie_nodes = []
        self.final_nodes = []
        
        # this is a temporary register to store node ids that needs to be
        # checked by certain functions
        self.standby_bin = []

        self.nodes_output_directory = nodes_output_directory
        
        self.outliers = {}
        self.outlier_reasons = []
        self.next_available_node_id = None
        
        self.average_read_length = None
        self.alignment_length    = None


    def get_new_node_id(self):
        if not self.next_available_node_id:
            new_node_id = 1
            self.next_available_node_id = new_node_id + 1
        else:
            new_node_id = self.next_available_node_id
            self.next_available_node_id += 1

        return '%.9d' % new_node_id


    def add_new_node(self, node_id, unique_read_objects_list, root = False, parent_id = None):
        if not self.nodes_output_directory:
            raise ConfigError, "Nodes output directory has to be declared before adding new nodes"

        node = Node(node_id, self.nodes_output_directory)

        node.reads = unique_read_objects_list
        node.size = sum([read.frequency for read in node.reads])
        node.pretty_id = self.get_pretty_id(node_id)

        if parent_id:
            parent = self.nodes[parent_id]
            parent.children.append(node.node_id)
            node.level = parent.level + 1
            node.parent = parent.node_id

        node.refresh()

        if root:
            # things to initialize if this is the root node
            node.level = 0

            self.alignment_length = len(node.reads[0].seq)
            
            # compute and store the average read length
            # FIXME: this is taking forever for large datasets. there must be a smarter way
            # to do this.
            read_lengths = []
            for read in node.reads:
                read_lengths.append(len(read.seq.replace('-', '')))
            self.average_read_length = int(round(numpy.mean(read_lengths)))

        self.nodes[node_id] = node

        return node


    def get_pretty_id(self, node_id):
        pretty_id = node_id
        while 1:
            if pretty_id[0] == '0':
                pretty_id = pretty_id[1:]
            else:
                break
        return pretty_id


    def get_node(self, node_id):
        return self.nodes[node_id]


    def print_node(self, node_id):
        node = self.nodes[node_id]
        print
        print 'Node "%s"' % node
        print '---------------------------------'
        print 'Alive     : %s' % (not node.killed)
        print 'Dirty     : %s' % node.dirty
        print 'Size      : %d' % node.size
        print 'Parent    : %s' % node.parent
        print 'Children  :', node.children
        print


    def get_final_count(self):
        return sum([sum([read.frequency for read in self.nodes[node_id].reads]) for node_id in self.final_nodes])
            

    def get_siblings(self, node_id):
        node = self.nodes[node_id]
        siblings = []
        
        parent_nodes_to_analyze = [self.get_node(node.parent)]
        
        while len(parent_nodes_to_analyze):
            parent = parent_nodes_to_analyze.pop(0)
            
            for candidate in [self.get_node(c) for c in parent.children if c != node.node_id]:
                if candidate.children:
                    parent_nodes_to_analyze.append(candidate)
                else:
                    siblings.append((candidate.size, candidate.node_id))

        # sort siblings least abundant to most
        siblings.sort()
        
        return [s[1] for s in siblings]


    def remove_node(self, node_id, store_content_in_outliers_dict = False, reason = None):
        node = self.nodes[node_id]
        parent = self.nodes[node.parent]
        
        parent.children.remove(node_id)

        if store_content_in_outliers_dict:
            for read in node.reads:
                self.store_outlier(read, reason)

        # get rid of node files.
        self.remove_node_files(node_id)
 
        # it is always sad to pop things
        self.nodes.pop(node_id)

        # and this recursion right here scares the shit out of me:
        if parent.node_id != 'root' and not parent.children:
            self.remove_node(parent.node_id)


    def store_outlier(self, unique_read_object, reason = 'unknown_reason'):
        if reason not in self.outlier_reasons:
            self.outlier_reasons.append(reason)
            self.outliers[reason] = set([])
            
        self.outliers[reason].add(unique_read_object)


    def remove_node_files(self, node_id):
        node = self.nodes[node_id]

        try:
            os.remove(node.alignment)
            os.remove(node.entropy_file)
            os.remove(node.unique_alignment)
        except:
            pass


    def merge_nodes(self, absorber_node_id, absorbed_node_id):
        # absorbed node gets merged into the absorber node
        absorber = self.get_node(absorber_node_id)
        absorbed = self.get_node(absorbed_node_id)
        
        absorber_parent = self.get_node(absorber.parent)
        absorbed_parent = self.get_node(absorbed.parent)
        
        # append read objects of absorbed to absorber:
        absorber.reads += absorbed.reads
        absorber.dirty = True
        
        # remove absorbed from the topology
        absorbed_parent.children.remove(absorbed.node_id)
        
        if absorber_parent.node_id != absorbed_parent.node_id and absorbed_parent.node_id != 'root':
            absorbed_parent.size -= absorbed.size
        
        # did the absorbed node's parent just become a final node?
        # if that's the case we gotta remove this from the topology, because reads in this intermediate
        # node was previously split between its child nodes. if all children were absorbed by other nodes
        # this node has no place in the topology anymore.
        if not absorbed_parent.children:
            self.remove_node(absorbed_parent.node_id)

        self.final_nodes.remove(absorbed.node_id)
        self.alive_nodes.remove(absorbed.node_id)

        # if absorbed was a identified as a zombie:
        if absorbed.node_id in self.zombie_nodes:
            self.zombie_nodes.remove(absorbed.node_id)
        
        # kill the absorbed
        absorbed.killed = True
        self.remove_node_files(absorbed.node_id)
        
        # refresh the absorbing node
        absorber.refresh()

        
    def get_parent_node(self, node_id):
        return self.nodes[self.nodes[node_id].parent]


    def update_final_nodes(self):
        self.alive_nodes = [n for n in sorted(self.nodes.keys()) if not self.nodes[n].killed]

        # get final nodes sorted by abundance        
        final_nodes_tpls = [(self.nodes[n].size, n) for n in self.alive_nodes if not self.nodes[n].children]
        final_nodes_tpls.sort(reverse = True)
        self.final_nodes = [n[1] for n in final_nodes_tpls]


    def store_final_nodes(self):
        for node_id in self.final_nodes:
            node = self.get_node(node_id)
            node.store()


    def recompute_nodes(self):
        for node_id in self.final_nodes:
            node = self.get_node(node_id)
            if node.dirty:
                node.refresh()


    def get_candidate_nodes_based_on_distance(self, sequence, max_levenshtein_ratio):
        # here we have a sequence, which is probably an outlier from the raw decomposition
        # and we want to find candidate nodes for this sequence with respect to the
        # maximum Levenshtein ratio. So, this function will find any node that has a rep
        # seq within the given radius of distance, and return them.
        import Levenshtein
        
        distance_node_tuples = []
        
        for node in [self.nodes[node_id] for node_id in self.final_nodes]:
            r = 1 - Levenshtein.ratio(node.representative_seq, sequence)
            if r < max_levenshtein_ratio:
                distance_node_tuples.append((r, node.node_id))
                
        return distance_node_tuples


    def get_best_matching_node(self, sequence, distance_node_tuples):
        # here we have a sequence, and a number of nodes that was previously decided to be OK
        # candidates for this read. this function will do the trick to find really the best one
        # among all, even if it contradicts with the distance (rep seq of one node can be more
        # distant from the read than another one, but the distant one may be a better node to put
        # the outlier read because it may be more appropriate for biological reasons, so it is a
        # good idea to align them, see whether differences coincide with discriminant locations
        # that were originally used for decomposition, etc)
        
        # FIXME: now we return the smallest distance, but it should get smarter at some point:
        distance_node_tuples.sort()
        return distance_node_tuples[0][1]


    def relocate_outlier(self, outlier_read_object, target_node_id, original_removal_reason):
        '''
            add an outlier read to an existing node (target_node_id).
                                                                        '''
        node = self.nodes[target_node_id]
        
        # update node alignment file with the outlier
        node.reads.append(outlier_read_object)
        node.dirty = True
        
        # remove outlier from outliers object
        self.outliers[original_removal_reason].remove(outlier_read_object)
        

class Node:
    def __init__(self, node_id, output_directory):
        self.node_id            = node_id
        self.pretty_id          = None
        self.reads              = []
        self.representative_seq = None
        self.killed             = False
        self.dirty              = False
        self.entropy            = None
        self.entropy_tpls       = None
        self.parent             = None
        self.children           = []
        self.discriminants      = None
        self.max_entropy        = None
        self.average_entropy    = None
        self.size               = 0
        self.level              = None
        self.density            = None
        self.freq_curve_img_path = None
        self.competing_unique_sequences_ratio = None
        self.file_path_prefix   = os.path.join(output_directory, node_id)
        self.alignment_path     = self.file_path_prefix + '.fa'
        self.unique_alignment_path = self.file_path_prefix + '.unique'


    def __str__(self):
        return self.pretty_id


    def set_representative(self):
        self.reads.sort(key=lambda x: x.frequency, reverse = True)
        self.representative_seq = self.reads[0].seq


    def do_entropy(self):
        self.entropy_tpls = []
        for position in range(0, len(self.representative_seq)):
            column = ''.join([read.seq[position] * read.frequency for read in self.reads])
            
            if len(set(column)) == 1:
                self.entropy_tpls.append((position, 0.0),)
            else:
                e = entropy(column)

                if e < 0.00001:
                    self.entropy_tpls.append((position, 0.0),)
                else:
                    self.entropy_tpls.append((position, e),)

        self.entropy = [t[1] for t in self.entropy_tpls]
        self.entropy_tpls = sorted(self.entropy_tpls, key=operator.itemgetter(1), reverse=True)
        self.max_entropy = max(self.entropy)
        self.average_entropy = numpy.mean([e for e in self.entropy if e > 0.05] or [0])


    def do_competing_unique_sequences_ratio_and_density(self):
        if len(self.reads) == 1:
            self.competing_unique_sequences_ratio = 0
        else:
            self.competing_unique_sequences_ratio = self.reads[1].frequency * 1.0 / self.reads[0].frequency
                    
        self.density = self.reads[0].frequency * 1.0 / self.size


    def refresh(self):
        self.set_representative()
        self.do_entropy()
        self.do_competing_unique_sequences_ratio_and_density()
        self.dirty = False


    def store(self):
        alignment = open(self.alignment_path, 'w')
        for read in self.reads:
            for read_id in read.ids:
                alignment.write('>%s\n%s\n' % (read_id, read.seq))
        alignment.close()

        unique_alignment = open(self.unique_alignment_path, 'w')
        for read in self.reads:
            unique_alignment.write('>%s|frequency:%d\n%s\n' % (read.ids[0], read.frequency, read.seq))
        unique_alignment.close()
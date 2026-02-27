import pandas as pd
import numpy as np
import networkx as nx
import os

def generate_coords():
    print("Loading distance matrices...")
    dist_objects = pd.read_csv('dist_objects.csv')
    dist_start = pd.read_csv('dist_start.csv')
    
    num_objects = len(dist_objects)
    full_dist_matrix = np.zeros((num_objects + 1, num_objects + 1))
    
    # Fill object-to-object distances
    dist_matrix_objs = dist_objects.select_dtypes(include=[np.number]).to_numpy()
    full_dist_matrix[1:, 1:] = dist_matrix_objs
    
    # Fill depot-to-object and object-to-depot distances
    dist_start_arr = dist_start['dist_start'].to_numpy()
    full_dist_matrix[0, 1:] = dist_start_arr
    full_dist_matrix[1:, 0] = dist_start_arr
    
    # Ensure symmetry just in case
    full_dist_matrix = (full_dist_matrix + full_dist_matrix.T) / 2
    full_dist_matrix[np.diag_indices_from(full_dist_matrix)] = 0
    
    print("Running Kamada-Kawai layout (force-directed) via NetworkX...")
    # Kamada-Kawai layout works well directly on distance matrices
    # Treat the distance matrix as shortest path distances
    G = nx.from_numpy_array(full_dist_matrix)
    
    # Use kamada_kawai_layout, which tries to map graph distances to geometric distances
    pos = nx.kamada_kawai_layout(G, dist=dict(nx.all_pairs_dijkstra_path_length(G, weight='weight')))
    
    # Extract coordinates
    coords = np.zeros((num_objects + 1, 2))
    for i in range(num_objects + 1):
        coords[i] = [pos[i][0], pos[i][1]]
    
    print("Saving to coords.csv...")
    coords_df = pd.DataFrame(coords, columns=['x', 'y'])
    coords_df.to_csv('coords.csv', index_label='node_id')
    print("Done!")

if __name__ == '__main__':
    generate_coords()


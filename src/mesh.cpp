#include "mesh.h"
#include <cmath>
#include <cstdlib>
#include <stdexcept>

Mesh::Mesh(int rows, int cols, float cell_size)
    : rows(rows), cols(cols), cell_size(cell_size),
      cells(rows * cols), T_buf(rows * cols), neighbors(rows * cols)
{
    // Initialize geometry: flat grid, z=0
    for (int r = 0; r < rows; r++) {
        for (int c = 0; c < cols; c++) {
            Cell& cell = at(r, c);
            cell.x = (c + 0.5f) * cell_size;
            cell.y = (r + 0.5f) * cell_size;
            cell.z = 0.0f;
            cell.base_size = cell_size;
            cell.T = T_AMBIENT;
            cell.is_boundary = (r == 0 || r == rows - 1 || c == 0 || c == cols - 1);
        }
    }
    buildNeighbors();
    T_buf.assign(rows * cols, T_AMBIENT);
}

void Mesh::buildNeighbors() {
    // Deltas for N, S, E, W neighbors
    const int dr[] = {-1, 1, 0, 0};
    const int dc[] = { 0, 0, 1,-1};

    for (int r = 0; r < rows; r++) {
        for (int c = 0; c < cols; c++) {
            NeighborList& nl = neighbors[idx(r, c)];
            nl.count = 0;
            for (int d = 0; d < 4; d++) {
                int nr = r + dr[d];
                int nc = c + dc[d];
                if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
                    nl.idx[nl.count++] = idx(nr, nc);
                } else {
                    nl.idx[d] = -1;
                }
            }
        }
    }
}

void Mesh::setTypedCell(Cell& cell, CellType type, float power_multiplier) {
    const CellTypeParams& p = CELL_TYPE_DEFAULTS[static_cast<int>(type)];
    cell.type  = type;
    cell.c     = p.c;
    cell.k     = p.k;
    cell.p     = p.p * power_multiplier;
    cell.alpha = p.alpha;
}

void Mesh::initFloorplan(FloorplanPattern pattern, unsigned seed) {
    std::srand(seed);

    switch (pattern) {

    case FloorplanPattern::UNIFORM:
        for (auto& cell : cells)
            setTypedCell(cell, CACHE, 1.0f);
        break;

    case FloorplanPattern::HOTSPOT_1: {
        // Base: all CACHE
        for (auto& cell : cells)
            setTypedCell(cell, CACHE, 1.0f);
        // ALU hotspot: 10% radius patch at center
        int cr = rows / 2, cc = cols / 2;
        int hr = std::max(1, rows / 10);
        int hc = std::max(1, cols / 10);
        for (int r = cr - hr; r <= cr + hr; r++)
            for (int c = cc - hc; c <= cc + hc; c++)
                if (r >= 0 && r < rows && c >= 0 && c < cols)
                    setTypedCell(at(r, c), ALU, 5.0f);
        break;
    }

    case FloorplanPattern::HOTSPOT_4: {
        // Base: all CACHE
        for (auto& cell : cells)
            setTypedCell(cell, CACHE, 1.0f);
        // Memory controller strip along top
        for (int c = 0; c < cols; c++)
            setTypedCell(at(0, c), MEMORY, 0.3f);
        // Four ALU hotspots at quadrant centers
        int qr[] = {rows/4, rows/4, 3*rows/4, 3*rows/4};
        int qc[] = {cols/4, 3*cols/4, cols/4, 3*cols/4};
        int hr = std::max(1, rows / 12);
        int hc = std::max(1, cols / 12);
        for (int q = 0; q < 4; q++)
            for (int r = qr[q] - hr; r <= qr[q] + hr; r++)
                for (int c = qc[q] - hc; c <= qc[q] + hc; c++)
                    if (r >= 0 && r < rows && c >= 0 && c < cols)
                        setTypedCell(at(r, c), ALU, 4.0f);
        // Interconnect strips between quadrants
        for (int r = 0; r < rows; r++) {
            if (at(r, cols/2).type == CACHE)
                setTypedCell(at(r, cols/2), INTERCONNECT, 1.0f);
        }
        for (int c = 0; c < cols; c++) {
            if (at(rows/2, c).type == CACHE)
                setTypedCell(at(rows/2, c), INTERCONNECT, 1.0f);
        }
        break;
    }

    case FloorplanPattern::RANDOM: {
        CellType types[] = {ALU, CACHE, MEMORY, INTERCONNECT};
        // Weighted random: 20% ALU, 40% Cache, 25% Memory, 15% Interconnect
        int weights[] = {20, 40, 25, 15};
        for (auto& cell : cells) {
            int roll = std::rand() % 100;
            CellType chosen = CACHE;
            int cumul = 0;
            for (int t = 0; t < 4; t++) {
                cumul += weights[t];
                if (roll < cumul) { chosen = types[t]; break; }
            }
            float pm = 0.5f + (std::rand() % 100) / 100.0f; // 0.5x to 1.5x
            setTypedCell(cell, chosen, pm);
        }
        break;
    }

    default:
        throw std::invalid_argument("Unknown floorplan pattern");
    }

    // Boundary cells: zero power, high heat sink (they dissipate to ambient)
    for (int r = 0; r < rows; r++)
        for (int c = 0; c < cols; c++)
            if (at(r, c).is_boundary)
                at(r, c).p = 0.0f;
}

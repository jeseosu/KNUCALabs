#include <iostream>
#include <vector>
using namespace std;
int n;
vector<vector<char>> rozmir;
vector<vector<bool>> visited;

int upr[] = {-1, 1, 0, 0};
int rightleftc[] = {0, 0, -1, 1};

int solve(int r, int c) {
    if (r < 0 || r >= n || c < 0 || c >= n) return 0;
    if (rozmir[r][c] == '*' || visited[r][c]) return 0;

    visited[r][c] = true;
    int countpoints = 1;

    for (int i = 0; i < 4; i++) {
        countpoints += solve(r + upr[i], c + rightleftc[i]);
    }
    return countpoints;
}

int main() {
    ios_base::sync_with_stdio(0);
    cin.tie(0);
    cout.tie(0);

    // example below, replace it with your solution
    cin >> n;
    rozmir.assign(n, vector<char>(n));
    visited.assign(n, vector<bool>(n, false));
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            cin >> rozmir[i][j];
        }
    }

    int r, c;
    cin >> r >> c;
    r-=1, c-=1;
    cout << solve(r, c);
    return 0;

}
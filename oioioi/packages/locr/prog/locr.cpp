#include <iostream>
#include <vector>
int main() {
    int n;
    std::cin >> n;
    std::vector<int> a(n);
    for (int i = 0; i < n; i++) std::cin >> a[i];
    bool ok = true;
    for (int i = 0; i + 1 < n; i++) if (a[i] > a[i + 1]) ok = false;
    std::cout << (ok ? "TAK" : "NIE") << "\n";
}
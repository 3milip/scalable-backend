#include <iostream>
int main() {
    int n, c = 0;
    std::cin >> n;
    for (int i = 0; i < n; i++) {
        int x;
        std::cin >> x;
        if (x > 0) c++;
    }
    std::cout << c << "\n";
}
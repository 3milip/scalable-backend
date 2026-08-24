#include <iostream>
int main() {
    int w;
    std::cin >> w;
    std::cout << (w >= 4 && w % 2 == 0 ? "TAK" : "NIE") << "\n";
}
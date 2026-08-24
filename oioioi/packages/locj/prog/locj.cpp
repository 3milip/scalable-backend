#include <iostream>
#include <string>
#include <algorithm>
int main() {
    std::string s;
    std::cin >> s;
    std::string r = s;
    std::reverse(r.begin(), r.end());
    std::cout << (s == r ? "TAK" : "NIE") << "\n";
}
# Compile in Linux with
g++ main.cpp analysis.cpp fundamentals.cpp metadata.cpp scoring.cpp summary.cpp yahoo.cpp -o ../bin/buy_opp -I../include -std=c++17 -O3 -lcurl -pthread
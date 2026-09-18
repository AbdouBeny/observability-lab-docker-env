# Lance 10 requêtes d'affilée
for i in {1:10}; do curl -X POST http://localhost:8080/checkout; echo ""; sleep 0.5; done

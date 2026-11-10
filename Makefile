.PHONY: test verify demo version

test:
	PYTHONPATH=. python3 -m unittest discover -s tests -v

verify:
	python3 -m affiliate_fanout --env ../content-factory/.env --verify --json

demo:
	python3 -m affiliate_fanout --env ../content-factory/.env \
	  --brand-url https://www.aviasales.com/ --trs 597672 \
	  --text "Deal: {url}" --platforms telegram,bluesky,telegraph --json

version:
	python3 -m affiliate_fanout --help | head -3

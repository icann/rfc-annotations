DIR=$(shell pwd)
CONTAINERNAME=rfc-annotations
IMAGENAME=icann/rfc-annotations
CURRENT_CONTAINER=$(shell docker ps -aq --filter name=${CONTAINERNAME})
CURRENT_IMAGE=$(shell docker image list --filter reference=${IMAGENAME} -q)

all: folders
	python3 program/pull_updates.py
	RFC_INDEX="YES" python3 -u program/main.py

generated-html local-config raw-originals raw-originals/drafts annotations/_generated:
	mkdir -p $@

folders: generated-html local-config raw-originals raw-originals/drafts annotations/_generated

annotations: folders
	python3 program/pull_updates.py
	RFC_FETCH_FILES="NO" python3 -u program/main.py

test: tests folders
	PYTHONWARNINGS="ignore" pytest -vv

docker-build:
	@if [ -z '$(CURRENT_IMAGE)' ] ; \
	then \
		docker build -t ${IMAGENAME} . ; \
	fi

docker-annotations: docker-build folders
	docker run --mount type=bind,src="$(DIR)/raw-originals",dst=/raw-originals \
	   --mount type=bind,src="$(DIR)/local-config",dst=/local-config \
	   --mount type=bind,src="$(DIR)/annotations",dst=/annotations \
	   --mount type=bind,src="$(DIR)/generated-html",dst=/generated-html \
	   -e RFC_FETCH_FILES="NO" \
	   --name ${CONTAINERNAME} --rm ${IMAGENAME}

docker: docker-build folders
	docker run --mount type=bind,src="$(DIR)/raw-originals",dst=/raw-originals \
       --mount type=bind,src="$(DIR)/local-config",dst=/local-config \
	   --mount type=bind,src="$(DIR)/annotations",dst=/annotations \
	   --mount type=bind,src="$(DIR)/generated-html",dst=/generated-html \
	   -e RFC_INDEX="YES" \
	   --name ${CONTAINERNAME} --rm ${IMAGENAME}

docker-remove:
	@if [ -n '$(CURRENT_CONTAINER)' ] ; \
	then \
		docker container rm ${CONTAINERNAME}; \
	fi
	@if [ -n '$(CURRENT_IMAGE)' ] ; \
	then \
		docker image rm ${IMAGENAME}; \
	fi

clean: docker-remove
	rm -rf generated-html && rm -rf raw-originals && rm -rf annotations/_generated && rm -rf .pytest_cache \
	rm -rf program/__pycache__
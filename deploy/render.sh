#!/bin/sh
# Builds the website and API images for Render's processors, pushes them to a registry, and creates or updates the three Render services.
# The facilitator image is built and published by github.com/useh402/facilitator; set FAC_IMAGE to pin a tag.
#
#   deploy/render.sh build            build linux/amd64 images, tagged with the git commit
#   deploy/render.sh push             push them to $REGISTRY (for example docker.io/yourname)
#   deploy/render.sh create           create the three services on Render (first time); create-backend / create-web do it in two steps
#   deploy/render.sh update           point the services at the new images (every later deploy)
#
# Secrets are read from api/.env.docker and .env.facilitator and sent to Render as environment variables.
# They are never printed. Required: REGISTRY=<registry/namespace>; optional: RENDER_REGION (default oregon), RENDER_PLAN (default starter).
set -eu
cd "$(dirname "$0")/.."
REGISTRY="${REGISTRY:?set REGISTRY, for example docker.io/yourname}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
REGION="${RENDER_REGION:-oregon}"
PLAN="${RENDER_PLAN:-starter}"
FAC_IMAGE="${FAC_IMAGE:-ghcr.io/useh402/facilitator:latest}"
API_NAME="${API_NAME:-humanapi-api}"; FAC_NAME="${FAC_NAME:-humanapi-facilitator}"; WEB_NAME="${WEB_NAME:-humanapi-web}"
API_URL="https://$API_NAME.onrender.com"; FAC_URL="https://$FAC_NAME.onrender.com"; WEB_URL="https://$WEB_NAME.onrender.com"
# Every origin the site is served from; the API refuses browser requests from any other.
CORS_ORIGINS="${CORS_ORIGINS:-$WEB_URL,https://h402.io,https://www.h402.io}"
PRIVY_APP_ID="$(grep '^NEXT_PUBLIC_PRIVY_APP_ID=' web/.env.local | cut -d= -f2-)"

envflags() {  # file -> --env-var K=V ... (no echo)
  grep -vE '^\s*(#|$)' "$1" | grep -vE '^(HA_HOST|HA_PORT|HF_HOST|HF_PORT|HA_FACILITATOR_URL|HA_CORS_ORIGINS|HA_DATABASE_URL_BACKUP|HA_SQLITE_BACKUP_URL)=' | sed -E "s/^([A-Z_]+)='(.*)'$/\1=\2/" | while IFS= read -r line; do printf -- "--env-var\n%s\n" "$line"; done
}

case "${1:-}" in
  build)
    docker buildx build --platform linux/amd64 -t "$REGISTRY/humanapi-api:$TAG" --load api
    docker buildx build --platform linux/amd64 -t "$REGISTRY/humanapi-web:$TAG" --load \
      --build-arg "NEXT_PUBLIC_API_URL=$API_URL" --build-arg "NEXT_PUBLIC_ROBINHOOD_NETWORK=eip155:4663" --build-arg "NEXT_PUBLIC_PRIVY_APP_ID=$PRIVY_APP_ID" --build-arg NEXT_PUBLIC_DEV_LOGIN=0 web
    echo "built $TAG" ;;
  push)
    for s in api web; do docker push "$REGISTRY/humanapi-$s:$TAG"; done ;;
  create|create-backend)
    # The facilitator first (the API needs its address), then the API, then the site.
    # shellcheck disable=SC2046
    render services create --name "$FAC_NAME" --type web_service --image "$FAC_IMAGE" --region "$REGION" --plan "$PLAN" --health-check-path /health --confirm -o text $(envflags .env.facilitator | tr '\n' ' ')
    render services create --name "$API_NAME" --type web_service --image "$REGISTRY/humanapi-api:$TAG" --region "$REGION" --plan "$PLAN" --health-check-path /v1/stats --confirm -o text \
      --env-var "HA_FACILITATOR_URL=$FAC_URL" --env-var "HA_CORS_ORIGINS=$CORS_ORIGINS" --env-var "HA_PUBLIC_BASE_URL=$API_URL" --env-var "HA_PUBLIC_CACHE_SECONDS=10" $(envflags api/.env.docker | tr '\n' ' ')
    [ "$1" = "create-backend" ] && exit 0
    render services create --name "$WEB_NAME" --type web_service --image "$REGISTRY/humanapi-web:$TAG" --region "$REGION" --plan "$PLAN" --health-check-path / --confirm -o text ;;
  create-web)
    render services create --name "$WEB_NAME" --type web_service --image "$REGISTRY/humanapi-web:$TAG" --region "$REGION" --plan "$PLAN" --health-check-path / --confirm -o text ;;
  update)
    for s in "$FAC_NAME=$FAC_IMAGE" "$API_NAME=$REGISTRY/humanapi-api:$TAG" "$WEB_NAME=$REGISTRY/humanapi-web:$TAG"; do
      name="${s%%=*}"; img="${s#*=}"
      render services update "$name" --image "$img" --confirm -o text
      sid="$(render services -o json | python3 -c "import sys,json; print(next(x.get('service',x)['id'] for x in json.load(sys.stdin) if x.get('service',x)['name']=='$name'))")"
      render deploys create "$sid" --confirm -o text  # changing the image does not deploy by itself
    done ;;
  *) echo "usage: deploy/render.sh build|push|create|update"; exit 2 ;;
esac

#!/bin/bash
set -e

echo "等待MongoDB主节点启动..."
sleep 5

MAX_RETRIES=30
RETRY_COUNT=0

until mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "错误: 无法连接到MongoDB主节点"
        exit 1
    fi
    echo "等待MongoDB主节点就绪... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "检查副本集状态..."
if mongosh --eval "rs.status().ok" --quiet | grep -q "^1$"; then
    echo "副本集已初始化，跳过"
    exit 0
fi

echo "初始化副本集..."
mongosh --eval "
rs.initiate({
  _id: 'tcm-replSet',
  version: 1,
  members: [
    { _id: 0, host: 'mongodb-primary:27017', priority: 2 },
    { _id: 1, host: 'mongodb-secondary1:27017', priority: 1 },
    { _id: 2, host: 'mongodb-secondary2:27017', priority: 1 }
  ]
})
"

echo "等待主节点选举..."
sleep 10

echo "创建数据库和用户..."
mongosh --eval "
db = db.getSiblingDB('admin');
db.auth('$MONGO_INITDB_ROOT_USERNAME', '$MONGO_INITDB_ROOT_PASSWORD');
db = db.getSiblingDB('tcm_formulas');
db.createUser({
  user: 'tcm_app',
  pwd: 'tcm_password',
  roles: [
    { role: 'readWrite', db: 'tcm_formulas' }
  ]
});
"

echo "副本集初始化完成！"

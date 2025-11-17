#!/bin/bash
set -e
echo "Starting MongoDB initialization for mongot..."

# Get environment variables with defaults
MONGOT_USER=${MONGOT_USER:-mongotUser}
MONGOT_PASSWORD=${MONGOT_PASSWORD:-mongotPassword}

if [ -z "$MONGOT_PASSWORD" ]; then
  echo "Error: MONGOT_PASSWORD environment variable is required"
  exit 1
fi

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
for i in {1..30}; do
  if mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
    echo "MongoDB is ready"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "MongoDB failed to become ready"
    exit 1
  fi
  sleep 1
done

sleep 2

# Initialize replicaset if not already initialized
echo "Initializing replicaset..."
mongosh --quiet --eval "
try {
  const status = rs.status();
  print('Replicaset already initialized');
  print('Replicaset status: ' + JSON.stringify(status.set));
} catch (error) {
  if (error.message.includes('no replset config has been received') || 
      error.message.includes('not yet initialized')) {
    print('Initializing new replicaset...');
    const result =     rs.initiate({
      _id: 'rs0',
      members: [
        { _id: 0, host: 'mongo:27017' }
      ]
    });
    print('Replicaset initialization initiated');
  } else {
    print('Error checking replicaset status: ' + error);
    throw error;
  }
}
"

# Wait for replicaset to be ready after initialization
echo "Waiting for replicaset to be ready..."
for i in {1..60}; do
  if mongosh --quiet --eval "
    try {
      const status = rs.status();
      if (status.members && status.members.length > 0) {
        const primary = status.members.find(m => m.stateStr === 'PRIMARY');
        if (primary) {
          print('PRIMARY found');
          quit(0);
        }
      }
      quit(1);
    } catch (e) {
      quit(1);
    }
  " > /dev/null 2>&1; then
    echo "Replicaset is ready with PRIMARY"
    break
  fi
  if [ $i -eq 60 ]; then
    echo "Warning: Replicaset may not be fully ready, but continuing..."
  fi
  sleep 1
done

sleep 2

# Create or update mongotUser
echo "Creating or updating mongotUser..."
mongosh --eval "
const adminDb = db.getSiblingDB('admin');
const username = '$MONGOT_USER';
const password = '$MONGOT_PASSWORD';

try {
  // Try to update existing user
  const existingUser = adminDb.getUser(username);
  if (existingUser) {
    adminDb.changeUserPassword(username, password);
    print('User ' + username + ' password updated successfully');
  }
} catch (error) {
  if (error.code === 11 || error.message.includes('not found')) {
    // User doesn't exist, create it
    try {
      adminDb.createUser({
        user: username,
        pwd: password,
        roles: [{ role: 'searchCoordinator', db: 'admin' }]
      });
      print('User ' + username + ' created successfully');
    } catch (createError) {
      print('Error creating user: ' + createError);
      throw createError;
    }
  } else {
    print('Error updating user: ' + error);
    throw error;
  }
}
"

echo "MongoDB initialization completed."


/* eslint-env mocha */
/* eslint max-nested-callbacks: ["error", 6] */
/* eslint-disable no-console */

'use strict'
const Libp2p = require('libp2p')
const TCP = require('libp2p-tcp')
const Mplex = require('libp2p-mplex')
const { NOISE } = require('libp2p-noise')
const crypto = require('crypto')
const KadDHT = require('libp2p-kad-dht')
const Bootstrap = require('libp2p-bootstrap')

const PeerStore = require('libp2p/src/peer-store')
const PeerId = require('peer-id')
const multihashes = require('multihashing-async').multihash
const RoutingTable = require('../../src/routing')
const Message = require('../../src/message')
const { convertBuffer } = require('../../src/utils')
const { sortClosestPeers } = require('../../src/utils')
const DHT = require('../../src')
const uint8ArrayFromString = require('uint8arrays/from-string')
const TestDHT = require('../utils/test-dht')

const NUM_PEERS = 10//e3 // Peers to create, not including us
const LATENCY_DEAD_NODE = 120e3 // How long dead nodes should take before erroring
const NUM_DEAD_NODES = Math.floor(NUM_PEERS * 0.3) // 30% undialable
const MAX_PEERS_KNOWN = Math.min(500, NUM_PEERS) // max number of peers a node should be aware of (capped at NUM_PEERS)
const MIN_PEERS_KNOWN = 10 // min number of peers a node should be aware of
const LATENCY_MIN = 100 // min time a good peer should take to respond
const LATENCY_MAX = 10e3 // max time a good peer should take to respond
const KValue = 20 // k Bucket size
const ALPHA = 6 // alpha concurrency
const QUERY_KEY = uint8ArrayFromString('a key to search for')
const RUNS = 3 // How many times the simulation should run
const VERBOSE = true // If true, some additional logs will run

let dhtKey
let network
let peers
let ourPeerId
let sortedPeers // Peers in the network sorted by closeness to QUERY_KEY
let topIds // Closest 20 peerIds in the network

  // Execute the simulation
  ; (async () => {
    console.log('Starting setup...')
    await setup()

    sortedPeers = await sortClosestPeers(peers, dhtKey)
    topIds = sortedPeers.slice(0, 20).map(peerId => peerId.toB58String())
    const topIdFilter = (value) => topIds.includes(value)

    console.log('Total Nodes=%d, Dead Nodes=%d, Max Siblings per Peer=%d', NUM_PEERS, NUM_DEAD_NODES, MAX_PEERS_KNOWN)
    console.log('Starting %d runs with concurrency %d...', RUNS, ALPHA)
    const topRunIds = []
    for (let i = 0; i < RUNS; i++) {
      const { closestPeers, runTime } = await GetClosestPeersSimulation()

      //const foundIds = closestPeers.map(peerId => peerId.toB58String())
      //const intersection = foundIds.filter(topIdFilter)
      //topRunIds.push(intersection)

      //console.log('Found %d of the top %d peers in %d ms', intersection.length, KValue, runTime)
    }

    //const commonTopIds = getCommonMembers(topRunIds)
    //console.log('All runs found %d common peers', commonTopIds.length)

    process.exit()
  })()

/**
 * Setup the data for the test
 */
async function setup() {
  dhtKey = await convertBuffer(QUERY_KEY)
  console.log("Dht key:", dhtKey)

  peers = await createPeers(NUM_PEERS + 1)
  console.log("Peers:", peers.length)
  ourPeerId = peers.shift()
  console.log("Our peerID:", ourPeerId.toB58String())

  // Create the network
  network = await MockNetwork(peers)
  console.log("Mock network:", network)
}

/**
 * @typedef ClosestPeersSimResult
 * @property {Array<PeerId>} closestPeers
 * @property {number} runTime Time in ms the query took
 */
const createNode = async () => {
  const node = await Libp2p.create({
    addresses: {
      listen: ['/ip4/0.0.0.0/tcp/0']
    },
    modules: {
      transport: [TCP],
      streamMuxer: [Mplex],
      connEncryption: [NOISE],
      dht: KadDHT,
    },
    config: {
      dht: {
        enabled: true
      }
    }
  })

  await node.start()
  return node
}

/**
 * @returns {ClosestPeersSimResult}
 */
async function GetClosestPeersSimulation() {
  //console.log(ourPeerId)
  const node = await createNode()
  const dht = new DHT({
    peerId: ourPeerId,
    registrar: node.registrar,
    peerStore: new PeerStore(ourPeerId),
    dialer: node.dialer,
    handle: () => { },
    on: () => { }
  }, {
    kBucketSize: KValue,
    concurrency: ALPHA,
    randomWalk: {
      enabled: false
    }
  })

  //Add random peers to our table
  const ourPeers = randomMembers(peers, randomInteger(MIN_PEERS_KNOWN, MAX_PEERS_KNOWN))
  for (const peer of ourPeers) {
    await dht._add(peer)
  }

  dht.network.sendRequest = (to, message, callback) => {
    const networkPeer = network.peers[to.toB58String()]
    let response = null

    if (networkPeer.routingTable) {
      response = new Message(message.type, new Uint8Array(0), message.clusterLevel)
      response.closerPeers = networkPeer.routingTable.closestPeers(dhtKey, KValue)
    }

    VERBOSE && console.log(`sendRequest latency:${networkPeer.latency} peerId:${to.toB58String()} closestPeers:${response ? response.closerPeers.length : null}`)

    return setTimeout(() => {
      if (response) {
        return callback(null, response)
      }
      callback(new Error('ERR_TIMEOUT'))
    }, networkPeer.latency)
  }

  // Start the dht
  await dht.start()

  const startTime = Date.now()
  const closestPeers = await dht.getClosestPeers(QUERY_KEY)
  const runTime = Date.now() - startTime
  console.log(closestPeers)
  //closestPeers.next().then(() => closestPeers.next());  // Prints "World"
  return { closestPeers, runTime }
}

/**
 * Create `num` PeerIds
 *
 * @param {integer} num - How many peers to create
 * @returns {Array<PeerId>}
 */
function createPeers(num) {
  const crypto = require('crypto')
  const peers = [...new Array(num)].map(() => {
    var b = crypto.randomBytes(34)
    var encoded = multihashes.encode(b, 'sha2-256')
    return PeerId.createFromB58String(
      multihashes.toB58String(encoded)
    )
  })

  return peers
}

/**
 * Creates a mock network
 *
 * @param {Array<PeerId>} peers
 * @returns {Network}
 */
async function MockNetwork(peers) {
  const network = {
    peers: {}
  }

  // Make nodes dead
  for (const peer of peers.slice(0, NUM_DEAD_NODES)) {
    network.peers[peer.toB58String()] = {
      latency: LATENCY_DEAD_NODE
    }
  }

  // Give the remaining nodes:
  for (const peer of peers.slice(NUM_DEAD_NODES)) {
    const netPeer = network.peers[peer.toB58String()] = {
      // dial latency
      latency: randomInteger(LATENCY_MIN, LATENCY_MAX),
      // random sibling peers from the full list
      routingTable: new RoutingTable(peer, KValue)
    }
    const siblings = randomMembers(peers, randomInteger(MIN_PEERS_KNOWN, MAX_PEERS_KNOWN))
    for (const peer of siblings) {
      await netPeer.routingTable.add(peer)
    }
  }

  return network
}

/**
 * Returns a random integer between `min` and `max`
 *
 * @param {number} min
 * @param {number} max
 * @returns {int}
 */
function randomInteger(min, max) {
  return Math.floor(Math.random() * (max - min)) + min
}

/**
 * Return a unique array of random `num` members from `list`
 *
 * @param {Array<any>} list - array to pull random members from
 * @param {number} num - number of random members to get
 * @returns {Array<any>}
 */
function randomMembers(list, num) {
  const randomMembers = []

  if (list.length < num) throw new Error(`cant get random members, ${num} is less than ${list.length}`)

  while (randomMembers.length < num) {
    const randomMember = list[Math.floor(Math.random() * list.length)]
    if (!randomMembers.includes(randomMember)) {
      randomMembers.push(randomMember)
    }
  }

  return randomMembers
}

/**
 * Finds the common members of all arrays
 *
 * @param {Array<Array>} arrays - An array of arrays to find common members
 * @returns {Array<any>}
 */
function getCommonMembers(arrays) {
  return arrays.shift().reduce(function (accumulator, val1) {
    if (accumulator.indexOf(val1) === -1 &&
      arrays.every(function (val2) {
        return val2.indexOf(val1) !== -1
      })
    ) {
      accumulator.push(val1)
    }

    return accumulator
  }, [])
}

export default function KnightCard({ knight }) {

  return (
    <div className="card">

      <h3>{knight.name}</h3>

      <div>
        Role: {knight.role}
      </div>

    </div>
  )
}

#pragma once

#include <TNL/Containers/Vector.h>
#include <TNL/Meshes/Grid.h>
#include "UpwindMomentumBase.h"

namespace TNL {

template< typename Mesh,
          typename Real = typename Mesh::RealType,
          typename Index = typename Mesh::IndexType >
class UpwindMomentumY
{
};

template< typename MeshReal,
          typename Device,
          typename MeshIndex,
          typename Real,
          typename Index >
class UpwindMomentumY< Meshes::Grid< 1, MeshReal, Device, MeshIndex >, Real, Index >
   : public UpwindMomentumBase< Meshes::Grid< 1, MeshReal, Device, MeshIndex >, Real, Index >
{
   public:

      typedef Meshes::Grid< 1, MeshReal, Device, MeshIndex > MeshType;
      typedef UpwindMomentumBase< MeshType, Real, Index > BaseType;
      
      using typename BaseType::RealType;
      using typename BaseType::IndexType;
      using typename BaseType::DeviceType;
      using typename BaseType::CoordinatesType;
      using typename BaseType::MeshFunctionType;
      using typename BaseType::MeshFunctionPointer;
      using typename BaseType::VelocityFieldType;
      using typename BaseType::VelocityFieldPointer;
      using BaseType::Dimensions;

      template< typename MeshFunction, typename MeshEntity >
      __cuda_callable__
      Real operator()( const MeshFunction& rho_v,
                       const MeshEntity& entity,
                       const RealType& time = 0.0 ) const
      {
         static_assert( MeshEntity::getEntityDimension() == 1, "Wrong mesh entity dimensions." ); 
         static_assert( MeshFunction::getEntitiesDimension() == 1, "Wrong preimage function" ); 
         //const typename MeshEntity::template NeighborEntities< 1 >& neighborEntities = entity.getNeighborEntities(); 

         return 0.0;
      }

      /*template< typename MeshEntity >
      __cuda_callable__
      Index getLinearSystemRowLength( const MeshType& mesh,
                                      const IndexType& index,
                                      const MeshEntity& entity ) const;

      template< typename MeshEntity, typename Vector, typename MatrixRow >
      __cuda_callable__
      void updateLinearSystem( const RealType& time,
                               const RealType& tau,
                               const MeshType& mesh,
                               const IndexType& index,
                               const MeshEntity& entity,
                               const MeshFunctionType& u,
                               Vector& b,
                               MatrixRow& matrixRow ) const;*/
};

template< typename MeshReal,
          typename Device,
          typename MeshIndex,
          typename Real,
          typename Index >
class UpwindMomentumY< Meshes::Grid< 2, MeshReal, Device, MeshIndex >, Real, Index >
   : public UpwindMomentumBase< Meshes::Grid< 2, MeshReal, Device, MeshIndex >, Real, Index >
{
   public:
      typedef Meshes::Grid< 2, MeshReal, Device, MeshIndex > MeshType;
      typedef UpwindMomentumBase< MeshType, Real, Index > BaseType;
      
      using typename BaseType::RealType;
      using typename BaseType::IndexType;
      using typename BaseType::DeviceType;
      using typename BaseType::CoordinatesType;
      using typename BaseType::MeshFunctionType;
      using typename BaseType::MeshFunctionPointer;
      using typename BaseType::VelocityFieldType;
      using typename BaseType::VelocityFieldPointer;
      using BaseType::Dimensions;

      template< typename MeshFunction, typename MeshEntity >
      __cuda_callable__
      Real operator()( const MeshFunction& u,
                       const MeshEntity& entity,
                       const RealType& time = 0.0 ) const
      {
         static_assert( MeshEntity::getEntityDimension() == 2, "Wrong mesh entity dimensions." ); 
         static_assert( MeshFunction::getEntitiesDimension() == 2, "Wrong preimage function" ); 
         const typename MeshEntity::template NeighborEntities< 2 >& neighborEntities = entity.getNeighborEntities(); 


         const RealType& hxInverse = entity.getMesh().template getSpaceStepsProducts< -1, 0 >(); 
         const RealType& hyInverse = entity.getMesh().template getSpaceStepsProducts< 0, -1 >(); 

         const IndexType& center = entity.getIndex(); 
         const IndexType& east   = neighborEntities.template getEntityIndex<  1,  0 >(); 
         const IndexType& west   = neighborEntities.template getEntityIndex< -1,  0 >(); 
         const IndexType& north  = neighborEntities.template getEntityIndex<  0,  1 >(); 
         const IndexType& south  = neighborEntities.template getEntityIndex<  0, -1 >();
         
         const RealType& pressure_center = this->pressure.template getData< DeviceType >()[ center ];
         const RealType& pressure_west   = this->pressure.template getData< DeviceType >()[ west ];
         const RealType& pressure_east   = this->pressure.template getData< DeviceType >()[ east ];
         const RealType& pressure_north  = this->pressure.template getData< DeviceType >()[ north ];
         const RealType& pressure_south  = this->pressure.template getData< DeviceType >()[ south ];
         
         const RealType& density_center = this->density.template getData< DeviceType >()[ center ];
         const RealType& density_west   = this->density.template getData< DeviceType >()[ west ];
         const RealType& density_east   = this->density.template getData< DeviceType >()[ east ];
         const RealType& density_north  = this->density.template getData< DeviceType >()[ north ];
         const RealType& density_south  = this->density.template getData< DeviceType >()[ south ];

         const RealType& velocity_x_center = this->velocity.template getData< DeviceType >()[ 0 ].template getData< DeviceType >()[ center ];
         const RealType& velocity_x_east   = this->velocity.template getData< DeviceType >()[ 0 ].template getData< DeviceType >()[ east ];
         const RealType& velocity_x_west   = this->velocity.template getData< DeviceType >()[ 0 ].template getData< DeviceType >()[ west ];

         const RealType& velocity_y_center = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ center ];
         const RealType& velocity_y_east   = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ east ];
         const RealType& velocity_y_west   = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ west ];
         const RealType& velocity_y_north  = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ north ];
         const RealType& velocity_y_south  = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ south ];          
         
         return -hxInverse * ( 
                                 this->positiveOtherMomentumFlux( density_center, velocity_y_center, velocity_x_center, pressure_center )
                               - this->positiveOtherMomentumFlux( density_west  , velocity_y_west  , velocity_x_west  , pressure_west   )
                               - this->negativeOtherMomentumFlux( density_center, velocity_y_center, velocity_x_center, pressure_center )
                               + this->negativeOtherMomentumFlux( density_east  , velocity_y_east  , velocity_x_east  , pressure_east   )
                             )
                -hyInverse * ( 
                                 this->positiveMainMomentumFlux( density_center, velocity_y_center, pressure_center )
                               - this->positiveMainMomentumFlux( density_south , velocity_y_south , pressure_south  )
                               - this->negativeMainMomentumFlux( density_center, velocity_y_center, pressure_center )
                               + this->negativeMainMomentumFlux( density_north , velocity_y_north , pressure_north  )
                             );
      }

      /*template< typename MeshEntity >
      __cuda_callable__
      Index getLinearSystemRowLength( const MeshType& mesh,
                                      const IndexType& index,
                                      const MeshEntity& entity ) const;

      template< typename MeshEntity, typename Vector, typename MatrixRow >
      __cuda_callable__
      void updateLinearSystem( const RealType& time,
                               const RealType& tau,
                               const MeshType& mesh,
                               const IndexType& index,
                               const MeshEntity& entity,
                               const MeshFunctionType& u,
                               Vector& b,
                               MatrixRow& matrixRow ) const;*/
};

template< typename MeshReal,
          typename Device,
          typename MeshIndex,
          typename Real,
          typename Index >
class UpwindMomentumY< Meshes::Grid< 3,MeshReal, Device, MeshIndex >, Real, Index >
   : public UpwindMomentumBase< Meshes::Grid< 3, MeshReal, Device, MeshIndex >, Real, Index >
{
   public:
      typedef Meshes::Grid< 3, MeshReal, Device, MeshIndex > MeshType;
      typedef UpwindMomentumBase< MeshType, Real, Index > BaseType;
      
      using typename BaseType::RealType;
      using typename BaseType::IndexType;
      using typename BaseType::DeviceType;
      using typename BaseType::CoordinatesType;
      using typename BaseType::MeshFunctionType;
      using typename BaseType::MeshFunctionPointer;
      using typename BaseType::VelocityFieldType;
      using typename BaseType::VelocityFieldPointer;
      using BaseType::Dimensions;      

      template< typename MeshFunction, typename MeshEntity >
      __cuda_callable__
      Real operator()( const MeshFunction& u,
                       const MeshEntity& entity,
                       const RealType& time = 0.0 ) const
      {
         static_assert( MeshEntity::getEntityDimension() == 3, "Wrong mesh entity dimensions." ); 
         static_assert( MeshFunction::getEntitiesDimension() == 3, "Wrong preimage function" ); 
         const typename MeshEntity::template NeighborEntities< 3 >& neighborEntities = entity.getNeighborEntities(); 
 
         const RealType& hxInverse = entity.getMesh().template getSpaceStepsProducts< -1, 0,  0 >(); 
         const RealType& hyInverse = entity.getMesh().template getSpaceStepsProducts< 0, -1,  0 >(); 
         const RealType& hzInverse = entity.getMesh().template getSpaceStepsProducts< 0,  0, -1 >();
 
         const IndexType& center = entity.getIndex(); 
         const IndexType& east   = neighborEntities.template getEntityIndex<  1,  0,  0 >(); 
         const IndexType& west   = neighborEntities.template getEntityIndex< -1,  0,  0 >(); 
         const IndexType& north  = neighborEntities.template getEntityIndex<  0,  1,  0 >(); 
         const IndexType& south  = neighborEntities.template getEntityIndex<  0, -1,  0 >();
         const IndexType& up     = neighborEntities.template getEntityIndex<  0,  0,  1 >(); 
         const IndexType& down   = neighborEntities.template getEntityIndex<  0,  0, -1 >();
         
         const RealType& pressure_center = this->pressure.template getData< DeviceType >()[ center ];
         const RealType& pressure_west   = this->pressure.template getData< DeviceType >()[ west ];
         const RealType& pressure_east   = this->pressure.template getData< DeviceType >()[ east ];
         const RealType& pressure_north  = this->pressure.template getData< DeviceType >()[ north ];
         const RealType& pressure_south  = this->pressure.template getData< DeviceType >()[ south ];
         const RealType& pressure_up     = this->pressure.template getData< DeviceType >()[ up ];
         const RealType& pressure_down   = this->pressure.template getData< DeviceType >()[ down ];
         
         const RealType& density_center = this->density.template getData< DeviceType >()[ center ];
         const RealType& density_west   = this->density.template getData< DeviceType >()[ west ];
         const RealType& density_east   = this->density.template getData< DeviceType >()[ east ];
         const RealType& density_north  = this->density.template getData< DeviceType >()[ north ];
         const RealType& density_south  = this->density.template getData< DeviceType >()[ south ];
         const RealType& density_up     = this->density.template getData< DeviceType >()[ up ];
         const RealType& density_down   = this->density.template getData< DeviceType >()[ down ];
         
         const RealType& velocity_x_center = this->velocity.template getData< DeviceType >()[ 0 ].template getData< DeviceType >()[ center ];
         const RealType& velocity_x_east   = this->velocity.template getData< DeviceType >()[ 0 ].template getData< DeviceType >()[ east ];
         const RealType& velocity_x_west   = this->velocity.template getData< DeviceType >()[ 0 ].template getData< DeviceType >()[ west ];

         const RealType& velocity_y_center = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ center ];
         const RealType& velocity_y_east   = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ east ];
         const RealType& velocity_y_west   = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ west ];
         const RealType& velocity_y_north  = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ north ];
         const RealType& velocity_y_south  = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ south ];
         const RealType& velocity_y_up     = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ up ];
         const RealType& velocity_y_down   = this->velocity.template getData< DeviceType >()[ 1 ].template getData< DeviceType >()[ down ];

         const RealType& velocity_z_center = this->velocity.template getData< DeviceType >()[ 2 ].template getData< DeviceType >()[ center ];
         const RealType& velocity_z_up     = this->velocity.template getData< DeviceType >()[ 2 ].template getData< DeviceType >()[ up ];
         const RealType& velocity_z_down   = this->velocity.template getData< DeviceType >()[ 2 ].template getData< DeviceType >()[ down ]; 

         return -hxInverse * ( 
                                 this->positiveOtherMomentumFlux( density_center, velocity_y_center, velocity_x_center, pressure_center )
                               - this->positiveOtherMomentumFlux( density_west  , velocity_y_west  , velocity_x_west  , pressure_west   )
                               - this->negativeOtherMomentumFlux( density_center, velocity_y_center, velocity_x_center, pressure_center )
                               + this->negativeOtherMomentumFlux( density_east  , velocity_y_east  , velocity_x_east  , pressure_east   )
                             )
                -hyInverse * ( 
                                 this->positiveMainMomentumFlux( density_center, velocity_y_center, pressure_center )
                               - this->positiveMainMomentumFlux( density_south , velocity_y_south , pressure_south  )
                               - this->negativeMainMomentumFlux( density_center, velocity_y_center, pressure_center )
                               + this->negativeMainMomentumFlux( density_north , velocity_y_north , pressure_north  )
                             )
                -hzInverse * ( 
                                 this->positiveOtherMomentumFlux( density_center, velocity_y_center, velocity_z_center, pressure_center )
                               - this->positiveOtherMomentumFlux( density_down  , velocity_y_down  , velocity_z_down  , pressure_down   )
                               - this->negativeOtherMomentumFlux( density_center, velocity_y_center, velocity_z_center, pressure_center )
                               + this->negativeOtherMomentumFlux( density_up    , velocity_y_up    , velocity_z_up    , pressure_up     )
                             );
      }

      /*template< typename MeshEntity >
      __cuda_callable__
      Index getLinearSystemRowLength( const MeshType& mesh,
                                      const IndexType& index,
                                      const MeshEntity& entity ) const;

      template< typename MeshEntity, typename Vector, typename MatrixRow >
      __cuda_callable__
      void updateLinearSystem( const RealType& time,
                               const RealType& tau,
                               const MeshType& mesh,
                               const IndexType& index,
                               const MeshEntity& entity,
                               const MeshFunctionType& u,
                               Vector& b,
                               MatrixRow& matrixRow ) const;*/
};


} // namespace TNL
